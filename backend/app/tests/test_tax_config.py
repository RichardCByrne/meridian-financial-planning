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
