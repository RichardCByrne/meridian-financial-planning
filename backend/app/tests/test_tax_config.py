"""Tax config: TaxConfig dataclass + per-plan custom configs."""

from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.config.tax_ie_2026 import IRELAND_2026_OFFICIAL
from app.db import SessionLocal
from app.engine.tax_config import TaxConfig
from app.main import app
from app.models import User


def _ensure_user(firebase_uid: str, email: str) -> User:
    with SessionLocal() as db:
        existing = db.query(User).filter(User.firebase_uid == firebase_uid).one_or_none()
        if existing is not None:
            return existing
        u = User(firebase_uid=firebase_uid, email=email, display_name=email)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u


@contextmanager
def _as_user(firebase_uid: str, email: str):
    user = _ensure_user(firebase_uid, email)

    def _override():
        with SessionLocal() as db:
            return db.query(User).filter(User.id == user.id).one()

    app.dependency_overrides[get_current_user] = _override
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------- TaxConfig dataclass round-trip ----------


def test_taxconfig_roundtrip_to_dict_and_back():
    d = IRELAND_2026_OFFICIAL.to_dict()
    rebuilt = TaxConfig.from_dict(d)
    # Frozen dataclasses with the same field values are equal.
    assert rebuilt == IRELAND_2026_OFFICIAL


def test_taxconfig_with_overrides_returns_modified_copy():
    bumped = IRELAND_2026_OFFICIAL.with_overrides(higher_rate=0.45)
    assert bumped.higher_rate == 0.45
    assert IRELAND_2026_OFFICIAL.higher_rate == 0.40  # original untouched


def test_taxconfig_from_dict_drops_unknown_keys():
    d = {**IRELAND_2026_OFFICIAL.to_dict(), "future_field_we_dont_know": 42}
    cfg = TaxConfig.from_dict(d)
    assert cfg == IRELAND_2026_OFFICIAL


# ---------- Engine threading ----------


def test_simulator_uses_passed_tax_config():
    """A custom TaxConfig with a higher higher_rate must yield more income tax."""
    from datetime import date

    from app.engine.simulator import (
        AssetInput,
        AssumptionsInput,
        ExpenseInput,
        IncomeInput,
        PersonInput,
        PlanInput,
        simulate,
    )

    base = PlanInput(
        base_year=2026,
        projection_years=2,
        people=[
            PersonInput(id=1, name="Alice", dob=date(1985, 1, 1), is_primary=True, life_expectancy=90)
        ],
        incomes=[
            IncomeInput(
                id=1, person_id=1, kind="employment", name="Salary",
                gross_amount=120_000, start_year=2026, end_year=None,
                escalation_rate=0.0, pays_prsi=True, pays_usc=True,
            )
        ],
        expenses=[ExpenseInput(id=1, name="Living", category="basic", amount=10_000,
                               start_year=2026, end_year=None, escalation_rate=0.0)],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=0, growth_rate=0,
                          cost_basis=0, owner_person_id=None)],
        assumptions=AssumptionsInput(),
    )
    rows_default = simulate(base)

    base_higher = PlanInput(
        **{**base.__dict__, "tax_config": IRELAND_2026_OFFICIAL.with_overrides(higher_rate=0.50)}
    )
    rows_higher = simulate(base_higher)

    # 50% top rate produces measurably more income tax on the same gross.
    assert rows_higher[0].income_tax > rows_default[0].income_tax


# ---------- API: list / create / update / delete ----------


def test_list_returns_only_official_and_owned():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")

    with TestClient(app) as client:
        # Alice creates a private config.
        with _as_user(alice.firebase_uid, alice.email or ""):
            client.post("/api/tax-configs", json={"name": "Alice's Budget 2027 estimate"})
            alice_list = client.get("/api/tax-configs").json()
            names = {c["name"] for c in alice_list}
            assert "Ireland 2026 (official)" in names
            assert "Alice's Budget 2027 estimate" in names

        # Bob doesn't see Alice's.
        with _as_user(bob.firebase_uid, bob.email or ""):
            bob_list = client.get("/api/tax-configs").json()
            names = {c["name"] for c in bob_list}
            assert "Ireland 2026 (official)" in names
            assert "Alice's Budget 2027 estimate" not in names


def test_official_config_is_read_only():
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            configs = client.get("/api/tax-configs").json()
            official = next(c for c in configs if c["is_official"])
            r = client.patch(
                f"/api/tax-configs/{official['id']}",
                json={"config": {"higher_rate": 0.99}},
            )
            assert r.status_code == 403
            r = client.delete(f"/api/tax-configs/{official['id']}")
            assert r.status_code == 403


def test_clone_and_edit_changes_projection_deterministically():
    alice = _ensure_user("alice-uid", "alice@example.com")

    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            # Seed plan + person + salary.
            plan = client.post(
                "/api/plans",
                json={"name": "Tax-config plan", "base_year": 2026, "projection_years": 2},
            ).json()
            person = client.post(
                f"/api/plans/{plan['id']}/people",
                json={"name": "Alice", "dob": "1985-01-01", "is_primary": True},
            ).json()
            client.post(
                f"/api/people/{person['id']}/income",
                json={"kind": "employment", "name": "Salary",
                      "gross_amount": 120_000, "start_year": 2026},
            )

            # Baseline projection.
            base_proj = client.get(f"/api/plans/{plan['id']}/projection").json()
            base_tax = base_proj["years"][0]["income_tax"]

            # Clone the official, bump the higher_rate to 50%.
            cloned = client.post(
                "/api/tax-configs",
                json={
                    "name": "50% top rate scenario",
                    "config": {"higher_rate": 0.50},
                },
            ).json()
            assert cloned["config"]["higher_rate"] == 0.50

            # Pin it on the plan.
            client.patch(f"/api/plans/{plan['id']}", json={"tax_config_id": cloned["id"]})
            new_proj = client.get(f"/api/plans/{plan['id']}/projection").json()
            new_tax = new_proj["years"][0]["income_tax"]
            assert new_tax > base_tax

            # Unpin (set back to null) → projection returns to baseline.
            client.patch(f"/api/plans/{plan['id']}", json={"tax_config_id": None})
            reset_proj = client.get(f"/api/plans/{plan['id']}/projection").json()
            assert reset_proj["years"][0]["income_tax"] == base_tax


def test_user_cannot_read_anothers_config():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")

    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            cfg = client.post("/api/tax-configs", json={"name": "Alice private"}).json()
        with _as_user(bob.firebase_uid, bob.email or ""):
            assert client.get(f"/api/tax-configs/{cfg['id']}").status_code == 404
            assert client.delete(f"/api/tax-configs/{cfg['id']}").status_code == 404


def test_user_cannot_pin_anothers_config_to_a_plan():
    """A plan may only pin the official config or one the caller owns — pinning
    another user's private config (on create or update) is rejected 404, closing
    the indirect info-leak via projection output."""
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")

    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            alice_cfg = client.post("/api/tax-configs", json={"name": "Alice private"}).json()

        with _as_user(bob.firebase_uid, bob.email or ""):
            # Create a plan pinning Alice's config → rejected.
            r = client.post(
                "/api/plans",
                json={"name": "Bob steal", "base_year": 2026, "projection_years": 2,
                      "tax_config_id": alice_cfg["id"]},
            )
            assert r.status_code == 404

            # Bob's own plan; try to update its pin to Alice's config → rejected.
            bob_plan = client.post(
                "/api/plans",
                json={"name": "Bob plan", "base_year": 2026, "projection_years": 2},
            ).json()
            r = client.patch(
                f"/api/plans/{bob_plan['id']}", json={"tax_config_id": alice_cfg["id"]}
            )
            assert r.status_code == 404

            # Official + Bob's own config are allowed.
            official = next(
                c for c in client.get("/api/tax-configs").json() if c["is_official"]
            )
            assert client.patch(
                f"/api/plans/{bob_plan['id']}", json={"tax_config_id": official["id"]}
            ).status_code == 200
            bob_cfg = client.post("/api/tax-configs", json={"name": "Bob private"}).json()
            assert client.patch(
                f"/api/plans/{bob_plan['id']}", json={"tax_config_id": bob_cfg["id"]}
            ).status_code == 200


def test_clone_and_import_drop_a_foreign_tax_config_pin():
    """Cloning a shared plan (or importing a crafted payload) must not carry over
    a pin to someone else's private config — that would re-open the projection
    info-leak on the hydrate path. A pin the new owner *does* own survives."""
    from app.auth import grant_plan_membership

    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")

    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            alice_cfg = client.post("/api/tax-configs", json={"name": "Alice private"}).json()
            alice_plan = client.post(
                "/api/plans",
                json={"name": "Alice pinned", "base_year": 2026, "projection_years": 2,
                      "tax_config_id": alice_cfg["id"]},
            ).json()

        # Share the plan with Bob as viewer so he can clone it.
        with SessionLocal() as db:
            grant_plan_membership(db, alice_plan["id"], bob.id, role="viewer")

        with _as_user(bob.firebase_uid, bob.email or ""):
            # Clone → foreign pin dropped.
            cloned = client.post(f"/api/plans/{alice_plan['id']}/clone").json()
            assert cloned["tax_config_id"] is None

            # Import a hand-crafted payload aimed at Alice's config → dropped.
            imported = client.post(
                "/api/plans/import",
                json={
                    "format_version": 1,
                    "plan": {"name": "Bob import", "base_year": 2026,
                             "projection_years": 2, "tax_config_id": alice_cfg["id"]},
                },
            ).json()
            assert imported["tax_config_id"] is None

        # Alice cloning her *own* pinned plan keeps the pin (she owns the config).
        with _as_user(alice.firebase_uid, alice.email or ""):
            own_clone = client.post(f"/api/plans/{alice_plan['id']}/clone").json()
            assert own_clone["tax_config_id"] == alice_cfg["id"]


def test_delete_user_config_unpins_dependent_plans():
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            cfg = client.post("/api/tax-configs", json={"name": "Temp config"}).json()
            plan = client.post(
                "/api/plans",
                json={"name": "Pinned plan", "base_year": 2026, "projection_years": 2,
                      "tax_config_id": cfg["id"]},
            ).json()
            assert client.delete(f"/api/tax-configs/{cfg['id']}").status_code == 204
            # Plan still loads — pin was nulled out.
            refreshed = client.get(f"/api/plans/{plan['id']}").json()
            assert refreshed["tax_config_id"] is None


def test_reseeding_official_config_is_a_noop_write():
    """The official tax config is rewritten only when it actually changes, so a
    cold-start re-seed doesn't churn the row (Neon storage hygiene)."""
    import json

    from sqlalchemy import select

    from app.main import _seed_official_tax_config
    from app.models import TaxConfigRow

    with TestClient(app):  # lifespan seeds the official row once
        _seed_official_tax_config()  # second call: must detect no change
        with SessionLocal() as db:
            rows = db.execute(
                select(TaxConfigRow).where(
                    TaxConfigRow.is_official.is_(True),
                    TaxConfigRow.name == IRELAND_2026_OFFICIAL.name,
                )
            ).scalars().all()
            assert len(rows) == 1  # no duplicate inserted
            # Persisted JSON matches the source after a round-trip (tuples→lists),
            # which is exactly the gate that skips the write.
            assert json.dumps(rows[0].config_json, sort_keys=True) == json.dumps(
                IRELAND_2026_OFFICIAL.to_dict(), sort_keys=True
            )
