import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.models import register_all_models  # noqa: F401  ensure models import
from app.routers import (
    assets,
    assumptions,
    benefits,
    bequests,
    children,
    expenses,
    goals,
    income,
    invites,
    liabilities,
    members,
    people,
    plans,
    projections,
    scenarios,
    tax_configs,
)


def _apply_lightweight_migrations() -> None:
    """Bridge pre-Alembic SQLite files to the Alembic baseline.

    Production (Postgres on Cloud Run) runs `alembic upgrade head` from the
    Dockerfile entrypoint and never enters this function with a meaningful
    diff. This is purely a local-dev convenience: if the SQLite file pre-dates
    Alembic, add the few columns the old `_apply_lightweight_migrations` was
    patching, then stamp `alembic_version` to head so future migrations apply.
    """
    insp = inspect(engine)
    tables = insp.get_table_names()
    if "assets" in tables:
        cols = {c["name"] for c in insp.get_columns("assets")}
        if "acquired_year" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE assets ADD COLUMN acquired_year INTEGER"))
        if "annual_contribution" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN annual_contribution FLOAT NOT NULL DEFAULT 0.0"
                ))
        if "contribution_pct_of_net_income" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN "
                    "contribution_pct_of_net_income FLOAT NOT NULL DEFAULT 0.0"
                ))
        if "contribution_pct_of_gross_income" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN "
                    "contribution_pct_of_gross_income FLOAT NOT NULL DEFAULT 0.0"
                ))
        if "avc_annual" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN avc_annual FLOAT NOT NULL DEFAULT 0.0"
                ))
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN avc_pct_of_gross FLOAT NOT NULL DEFAULT 0.0"
                ))
        if "contribution_start_year" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN contribution_start_year INTEGER"
                ))
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN contribution_end_year INTEGER"
                ))
        if "purchase_year" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE assets ADD COLUMN purchase_year INTEGER"))
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN deposit FLOAT NOT NULL DEFAULT 0.0"
                ))
                conn.execute(text("ALTER TABLE assets ADD COLUMN disposal_year INTEGER"))
        if "linked_liability_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE assets ADD COLUMN linked_liability_id INTEGER"))
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN stamp_duty_pct FLOAT NOT NULL DEFAULT 0.0"
                ))
                conn.execute(text(
                    "ALTER TABLE assets ADD COLUMN selling_cost_pct FLOAT NOT NULL DEFAULT 0.0"
                ))
    if "people" in tables:
        cols = {c["name"] for c in insp.get_columns("people")}
        if "retirement_age" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE people ADD COLUMN retirement_age INTEGER"))
    if "assumptions" in tables:
        cols = {c["name"] for c in insp.get_columns("assumptions")}
        if "state_pension_annual_amount" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE assumptions ADD COLUMN state_pension_annual_amount "
                        "FLOAT NOT NULL DEFAULT 15044.0"
                    )
                )
    if "income_sources" in tables:
        cols = {c["name"] for c in insp.get_columns("income_sources")}
        if "employer_pension_contribution_pct" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE income_sources ADD COLUMN "
                        "employer_pension_contribution_pct FLOAT NOT NULL DEFAULT 0.0"
                    )
                )
        if "is_bonus" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE income_sources ADD COLUMN "
                        "is_bonus BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
    if "plans" in tables:
        cols = {c["name"] for c in insp.get_columns("plans")}
        if "tax_config_id" not in cols:
            with engine.begin() as conn:
                # SQLite can't add a FK constraint inline post-hoc, but the
                # plain INTEGER column is enough for the ORM to read/write.
                conn.execute(text("ALTER TABLE plans ADD COLUMN tax_config_id INTEGER"))
        if "filing_status" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE plans ADD COLUMN filing_status VARCHAR(20)"))
        if "onboarding_complete" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE plans ADD COLUMN "
                        "onboarding_complete BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
    if "people" in tables:
        cols = {c["name"] for c in insp.get_columns("people")}
        if "claims_rent_credit" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE people ADD COLUMN "
                        "claims_rent_credit BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
        if "lump_sum_pct" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE people ADD COLUMN "
                        "lump_sum_pct FLOAT NOT NULL DEFAULT 0.25"
                    )
                )
        if "prsi_weeks_at_base_year" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE people ADD COLUMN "
                        "prsi_weeks_at_base_year INTEGER NOT NULL DEFAULT 2080"
                    )
                )
        if "homecaring_weeks_at_base_year" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE people ADD COLUMN "
                        "homecaring_weeks_at_base_year INTEGER NOT NULL DEFAULT 0"
                    )
                )
        if "arf_target_drawdown_pct" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE people ADD COLUMN arf_target_drawdown_pct FLOAT")
                )
        if "pension_option" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE people ADD COLUMN "
                        "pension_option VARCHAR NOT NULL DEFAULT 'arf'"
                    )
                )
        if "annuity_rate" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE people ADD COLUMN annuity_rate FLOAT NOT NULL DEFAULT 0.04")
                )
    # children + benefits tables are picked up by Base.metadata.create_all on
    # the dev path (whole-table additions need no ALTER bridging). Per-child
    # rearing-cost columns added later DO need bridging on an existing children
    # table.
    if "children" in tables:
        cols = {c["name"] for c in insp.get_columns("children")}
        if "childcare_annual" not in cols:
            with engine.begin() as conn:
                for col in (
                    "childcare_annual",
                    "primary_annual",
                    "secondary_annual",
                    "secondary_private_fee_annual",
                    "everyday_annual",
                ):
                    conn.execute(
                        text(f"ALTER TABLE children ADD COLUMN {col} FLOAT NOT NULL DEFAULT 0.0")
                    )
                conn.execute(
                    text(
                        "ALTER TABLE children ADD COLUMN "
                        "secondary_is_private BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
    if "liabilities" in tables:
        cols = {c["name"] for c in insp.get_columns("liabilities")}
        if "monthly_overpayment" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE liabilities ADD COLUMN "
                        "monthly_overpayment FLOAT NOT NULL DEFAULT 0.0"
                    )
                )
    if "assumptions" in tables:
        cols = {c["name"] for c in insp.get_columns("assumptions")}
        if "state_pension_escalation_rate" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE assumptions ADD COLUMN "
                        "state_pension_escalation_rate FLOAT NOT NULL DEFAULT 0.015"
                    )
                )

    # Re-stamp Alembic to head so a dev DB that's been kept up via these
    # lightweight patches doesn't try to re-create tables on the next
    # `alembic upgrade head`. Production never enters this path — it runs
    # alembic from the Dockerfile entrypoint.
    if tables:
        try:
            from alembic import command
            from alembic.config import Config

            from pathlib import Path

            root = Path(__file__).resolve().parent.parent
            cfg = Config(str(root / "alembic.ini"))
            cfg.set_main_option("script_location", str(root / "alembic"))
            command.stamp(cfg, "head")
        except Exception as e:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning(
                "Could not stamp Alembic version on legacy SQLite DB: %s", e
            )


def _seed_official_tax_config() -> None:
    """Idempotently insert the IRELAND_2026_OFFICIAL row if missing."""
    from app.config.tax_ie_2026 import IRELAND_2026_OFFICIAL
    from app.db import SessionLocal
    from app.models import TaxConfigRow

    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.execute(
            select(TaxConfigRow).where(
                TaxConfigRow.is_official.is_(True),
                TaxConfigRow.name == IRELAND_2026_OFFICIAL.name,
            ).order_by(TaxConfigRow.id)
        ).scalars().all()
        if rows:
            # Keep the oldest row, drop any duplicates from earlier crashed boots.
            keeper, *dupes = rows
            desired = IRELAND_2026_OFFICIAL.to_dict()
            # Only write when something actually changed. Rewriting the row on
            # every boot (the app cold-starts often on Cloud Run with
            # min-instances=0) churns dead tuples + WAL that Neon retains in its
            # history window — needless storage for a no-op. Compare via JSON so
            # tuples (tax bands) match the lists round-tripped from the DB.
            import json

            same = json.dumps(keeper.config_json, sort_keys=True) == json.dumps(
                desired, sort_keys=True
            )
            if dupes or not same:
                for d in dupes:
                    db.delete(d)
                keeper.config_json = desired
                db.commit()
            return
        db.add(
            TaxConfigRow(
                name=IRELAND_2026_OFFICIAL.name,
                is_official=True,
                created_by_user_id=None,
                config_json=IRELAND_2026_OFFICIAL.to_dict(),
            )
        )
        db.commit()


def _adopt_orphan_plans() -> None:
    """In dev-mode, hand any pre-auth plans to the seeded dev user."""
    from app.auth import assign_orphan_plans_to_dev_user
    from app.db import SessionLocal

    with SessionLocal() as db:
        adopted = assign_orphan_plans_to_dev_user(db)
        if adopted:
            import logging

            logging.getLogger(__name__).info(
                "Phase 8 migration: assigned %d orphan plan(s) to the dev user.", adopted
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    register_all_models()
    # SQLite dev path only. Production runs alembic upgrade head from the
    # Dockerfile entrypoint; running create_all + stamp again on Postgres can
    # stall the lifespan past Cloud Run's startup probe budget.
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        _apply_lightweight_migrations()
    _seed_official_tax_config()
    _adopt_orphan_plans()
    yield


app = FastAPI(
    title="Meridian API",
    version="0.1.0",
    description="Meridian — financial planning API (Ireland 2026 tax engine).",
    lifespan=lifespan,
)

_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Liveness + DB readiness. Returns 503 if the DB is unreachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).warning("Health check DB ping failed: %s", e)
        raise HTTPException(status_code=503, detail="Database not reachable") from e
    return {"status": "ok", "db": "ok"}


app.include_router(plans.router, prefix="/api")
app.include_router(bequests.router, prefix="/api")
app.include_router(children.router, prefix="/api")
app.include_router(benefits.router, prefix="/api")
app.include_router(people.router, prefix="/api")
app.include_router(assumptions.router, prefix="/api")
app.include_router(income.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(liabilities.router, prefix="/api")
app.include_router(goals.router, prefix="/api")
app.include_router(scenarios.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(invites.router, prefix="/api")
app.include_router(tax_configs.router, prefix="/api")
app.include_router(projections.router, prefix="/api")
