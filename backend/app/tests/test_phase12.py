"""Phase 12 tests: CAT engine, death events, bequest CRUD."""

from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.config.tax_ie_2026 import IRELAND_2026_OFFICIAL
from app.db import SessionLocal
from app.engine import cat_ie
from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    BequestInput,
    ExpenseInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)
from app.main import app
from app.models import User


# ---------- helpers ----------


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


# ---------- CAT engine unit tests ----------


def test_cat_group_a_above_threshold():
    """€2M inheritance to Group A child: CAT = (2M − 400k) × 33%."""
    cat = cat_ie.compute_cat(2_000_000, "A", 0.0, IRELAND_2026_OFFICIAL)
    assert cat == pytest.approx((2_000_000 - 400_000) * 0.33, abs=1)


def test_cat_group_a_below_threshold():
    """€200k to Group A: no CAT — below the €400k threshold."""
    cat = cat_ie.compute_cat(200_000, "A", 0.0, IRELAND_2026_OFFICIAL)
    assert cat == 0.0


def test_cat_exempt_group():
    """Spouse (exempt) — no CAT regardless of amount."""
    cat = cat_ie.compute_cat(5_000_000, "exempt", 0.0, IRELAND_2026_OFFICIAL)
    assert cat == 0.0


def test_cat_lifetime_aggregation():
    """Two separate inheritances in Group A: threshold applied cumulatively."""
    # First receipt: €300k — below threshold (no tax)
    cat1 = cat_ie.compute_cat(300_000, "A", 0.0, IRELAND_2026_OFFICIAL)
    assert cat1 == 0.0

    # Second receipt: €200k — total now €500k, taxable portion = 500k − 400k = 100k
    cat2 = cat_ie.compute_cat(200_000, "A", 300_000.0, IRELAND_2026_OFFICIAL)
    assert cat2 == pytest.approx(100_000 * 0.33, abs=1)


def test_cat_group_c_small_threshold():
    """Group C (unrelated) — €20k threshold, everything above is taxed."""
    cat = cat_ie.compute_cat(50_000, "C", 0.0, IRELAND_2026_OFFICIAL)
    assert cat == pytest.approx((50_000 - 20_000) * 0.33, abs=1)


# ---------- Simulator death-event tests ----------


def _simple_person(id: int, birth_year: int, life_exp: int, name: str = "P") -> PersonInput:
    return PersonInput(
        id=id,
        name=name,
        dob=date(birth_year, 1, 1),
        is_primary=id == 1,
        life_expectancy=life_exp,
    )


def _salary(id: int, person_id: int, amount: float, start: int) -> IncomeInput:
    return IncomeInput(
        id=id,
        person_id=person_id,
        kind="employment",
        name="Salary",
        gross_amount=amount,
        start_year=start,
        end_year=None,
        escalation_rate=0.0,
        pays_prsi=True,
        pays_usc=True,
    )


def test_death_suppresses_income():
    """A person with life_expectancy = base_year generates no income."""
    # Born 1956, so in base_year 2026 they're age 70 = life_expectancy
    plan = PlanInput(
        base_year=2026,
        projection_years=3,
        people=[_simple_person(1, 1956, 70, "Mortal")],
        incomes=[_salary(1, 1, 60_000, 2026)],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=100_000, growth_rate=0.0, cost_basis=0)],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # In base year (2026) age = 70 = life_expectancy — person dies, no income
    assert rows[0].gross_income_total == 0.0
    assert rows[1].gross_income_total == 0.0  # still dead
    assert any("Mortal passes" in n for n in rows[0].notes)


def test_death_transfers_estate_to_internal_beneficiary():
    """On death the estate is transferred minus CAT to the internal beneficiary."""
    # Person A (id=1): born 1946, dies at age 80 in 2026
    # Person B (id=2): born 1986, the beneficiary
    # A has €1M cash, bequest 100% to B, Group A, no prior receipts
    expected_estate = 1_000_000.0
    expected_cat = cat_ie.compute_cat(expected_estate, "A", 0.0, IRELAND_2026_OFFICIAL)
    expected_net = expected_estate - expected_cat

    plan = PlanInput(
        base_year=2026,
        projection_years=2,
        people=[
            _simple_person(1, 1946, 80, "Alice"),
            _simple_person(2, 1986, 90, "Bob"),
        ],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="Alice cash", kind="cash", value=expected_estate,
                       growth_rate=0.0, cost_basis=0.0, owner_person_id=1),
        ],
        bequests=[
            BequestInput(id=1, from_person_id=1, to_person_id=2, cat_group="A", share_pct=1.0)
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)

    # Estate transferred in year 0
    assert rows[0].estate_transfers.get(1) == pytest.approx(expected_estate, rel=1e-4)
    assert rows[0].cat_paid == pytest.approx(expected_cat, abs=1)
    # Net worth includes what Bob received (net of CAT)
    assert rows[0].net_worth >= expected_net * 0.99


def test_external_bequest_removes_value_from_plan():
    """An external bequest (to_person_id=None) removes the share from net worth."""
    initial = 1_000_000.0
    plan = PlanInput(
        base_year=2026,
        projection_years=2,
        people=[_simple_person(1, 1946, 80, "Alice")],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=initial, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        bequests=[
            BequestInput(id=1, from_person_id=1, to_person_id=None, cat_group="A", share_pct=1.0)
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # All value left the plan — net worth near zero
    assert rows[0].net_worth < 1_000.0
    assert rows[0].cat_paid == 0.0


def test_no_bequest_means_estate_is_zeroed():
    """A person with no bequests: estate is wiped out (unallocated shares leave plan)."""
    plan = PlanInput(
        base_year=2026,
        projection_years=2,
        people=[_simple_person(1, 1946, 80, "Alice")],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=500_000, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        bequests=[],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # With no bequests the estate value is still recorded
    assert rows[0].estate_transfers.get(1) == pytest.approx(500_000, rel=1e-4)
    # But it went nowhere — net worth is near zero
    assert rows[0].net_worth < 1_000.0


# ---------- Bequest CRUD API tests ----------


def test_bequest_crud_round_trip():
    """Create, read, patch, and delete a bequest via the API."""
    alice = _ensure_user("alice-bequest-uid", "alice-bequest@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            plan = client.post(
                "/api/plans",
                json={"name": "Legacy plan", "base_year": 2026, "projection_years": 40},
            ).json()
            p1 = client.post(
                f"/api/plans/{plan['id']}/people",
                json={"name": "Parent", "dob": "1950-01-01", "life_expectancy": 85},
            ).json()
            p2 = client.post(
                f"/api/plans/{plan['id']}/people",
                json={"name": "Child", "dob": "1980-01-01", "life_expectancy": 90},
            ).json()

            # Create
            bequest = client.post(
                f"/api/plans/{plan['id']}/bequests",
                json={"from_person_id": p1["id"], "to_person_id": p2["id"],
                      "cat_group": "A", "share_pct": 0.75},
            ).json()
            assert bequest["share_pct"] == 0.75
            assert bequest["cat_group"] == "A"

            # List
            blist = client.get(f"/api/plans/{plan['id']}/bequests").json()
            assert len(blist) == 1

            # Patch
            updated = client.patch(
                f"/api/bequests/{bequest['id']}",
                json={"share_pct": 0.5, "notes": "Half to child"},
            ).json()
            assert updated["share_pct"] == 0.5
            assert updated["notes"] == "Half to child"

            # Delete
            assert client.delete(f"/api/bequests/{bequest['id']}").status_code == 204
            assert client.get(f"/api/plans/{plan['id']}/bequests").json() == []


def test_bequest_in_projection():
    """A bequest wired to a plan affects the projection — CAT shows in estate year."""
    alice = _ensure_user("alice-proj-bequest-uid", "alice-proj-bequest@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            plan = client.post(
                "/api/plans",
                json={"name": "Bequest projection", "base_year": 2026, "projection_years": 10},
            ).json()
            # Parent born 1946: dies in 2026 (age 80)
            p1 = client.post(
                f"/api/plans/{plan['id']}/people",
                json={"name": "Parent", "dob": "1946-01-01", "life_expectancy": 80},
            ).json()
            p2 = client.post(
                f"/api/plans/{plan['id']}/people",
                json={"name": "Child", "dob": "1986-01-01", "life_expectancy": 90},
            ).json()
            client.post(
                f"/api/plans/{plan['id']}/assets",
                json={"name": "Cash", "kind": "cash", "value": 500_000,
                      "owner_person_id": p1["id"]},
            )
            client.post(
                f"/api/plans/{plan['id']}/bequests",
                json={"from_person_id": p1["id"], "to_person_id": p2["id"],
                      "cat_group": "A", "share_pct": 1.0},
            )

            proj = client.get(f"/api/plans/{plan['id']}/projection").json()
            year0 = proj["years"][0]
            # Estate should be recorded in year 2026
            assert str(p1["id"]) in year0["estate_transfers"] or p1["id"] in year0.get("estate_transfers", {})
            assert year0["cat_paid"] > 0
