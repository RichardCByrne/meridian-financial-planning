"""Benefit-in-kind (BIK): cash-equivalent maths, simulator tax treatment, and
the CRUD + projection API.

BIK is employer-provided notional pay — taxed (IT + USC + PRSI) but never
received as cash and never paid by the household. Employer-paid medical
insurance additionally grants the 20% (capped) relief credit.
"""

from contextlib import contextmanager
from datetime import date

from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.config.tax_ie_2026 import IRELAND_2026_OFFICIAL as CFG
from app.db import SessionLocal
from app.engine import bik_ie
from app.engine.simulator import (
    AssumptionsInput,
    BenefitInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)
from app.main import app
from app.models import User


# --------------------------------------------------------------------------
# Pure cash-equivalent maths (engine/bik_ie.py)
# --------------------------------------------------------------------------


def test_medical_insurance_cash_equivalent_is_the_premium():
    assert bik_ie.cash_equivalent(kind="medical_insurance", amount=1_500) == 1_500


def test_company_car_uses_omv_times_rate():
    # Explicit rate overrides the default mid-band rate.
    assert bik_ie.cash_equivalent(kind="company_car", omv=40_000, rate=0.30) == 12_000


def test_company_car_falls_back_to_default_rate():
    assert bik_ie.cash_equivalent(kind="company_car", omv=40_000) == 40_000 * CFG.bik_company_car_default_rate


def test_company_van_uses_statutory_rate():
    assert bik_ie.cash_equivalent(kind="company_van", omv=30_000) == 30_000 * CFG.bik_company_van_rate


def test_preferential_loan_charges_rate_shortfall():
    # €100k home loan at 1% charged vs 4% qualifying specified rate → 3% BIK.
    ce = bik_ie.cash_equivalent(
        kind="preferential_loan", amount=100_000, rate=0.01, loan_is_qualifying=True
    )
    assert abs(ce - 100_000 * (0.04 - 0.01)) < 1e-6


def test_preferential_loan_non_qualifying_uses_higher_rate():
    ce = bik_ie.cash_equivalent(
        kind="preferential_loan", amount=10_000, rate=0.0, loan_is_qualifying=False
    )
    assert abs(ce - 10_000 * CFG.bik_preferential_loan_rate_other) < 1e-6


def test_preferential_loan_no_benefit_when_charged_above_specified():
    ce = bik_ie.cash_equivalent(
        kind="preferential_loan", amount=10_000, rate=0.20, loan_is_qualifying=True
    )
    assert ce == 0.0


def test_medical_insurance_relief_capped_per_adult():
    # €3,000 premium for one adult → relief = 20% of min(3000, 1000) = €200.
    assert bik_ie.medical_insurance_relief(3_000, adults=1, children=0) == 200.0


def test_medical_insurance_relief_under_cap():
    # €800 premium for one adult → 20% of 800 = €160 (below the €1,000 cap).
    assert bik_ie.medical_insurance_relief(800, adults=1, children=0) == 160.0


def test_medical_insurance_relief_children_raise_cap():
    # 2 adults + 1 child cap = 2*1000 + 1*500 = 2500; €4,000 premium → 20% of 2500.
    assert bik_ie.medical_insurance_relief(4_000, adults=2, children=1) == 500.0


# --------------------------------------------------------------------------
# Simulator tax treatment
# --------------------------------------------------------------------------


def _plan_with_benefit(benefit: BenefitInput | None, gross: float = 60_000) -> PlanInput:
    person = PersonInput(
        id=1, name="Worker", dob=date(1985, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    income = IncomeInput(
        id=1, person_id=1, kind="employment", name="Job",
        gross_amount=gross, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
    )
    return PlanInput(
        base_year=2026, projection_years=1,
        people=[person], incomes=[income], expenses=[], assets=[],
        benefits=[benefit] if benefit else [],
        assumptions=AssumptionsInput(inflation_rate=0.0, state_pension_escalation_rate=0.0),
    )


def test_bik_raises_tax_but_not_cash_gross():
    """A company-car BIK raises IT/USC/PRSI but the reported gross stays the
    cash salary (the benefit is notional), and the BIK total is surfaced."""
    base = simulate(_plan_with_benefit(None))[0]
    car = BenefitInput(
        id=1, person_id=1, kind="company_car", name="Car",
        start_year=2026, end_year=None, omv=40_000, rate=0.30,  # €12,000 BIK
    )
    withb = simulate(_plan_with_benefit(car))[0]

    # Reported gross is unchanged (BIK is not cash).
    assert abs(withb.gross_income_total - base.gross_income_total) < 1
    # The BIK is surfaced on its own channel.
    assert abs(withb.benefits_in_kind_total - 12_000) < 1
    # Tax went up (12k charged at the 40% marginal band + USC + PRSI).
    assert withb.total_tax > base.total_tax
    # Net income falls by exactly the extra tax (cash gross unchanged).
    extra_tax = withb.total_tax - base.total_tax
    assert abs((base.net_income_total - withb.net_income_total) - extra_tax) < 1


def test_bik_charged_to_all_three_taxes():
    """Compared to no-BIK, income tax, USC and PRSI all rise."""
    base = simulate(_plan_with_benefit(None))[0]
    other = BenefitInput(
        id=1, person_id=1, kind="other", name="Perk",
        start_year=2026, end_year=None, amount=5_000,
    )
    withb = simulate(_plan_with_benefit(other))[0]
    assert withb.income_tax > base.income_tax
    assert withb.usc > base.usc
    assert withb.prsi > base.prsi


def test_medical_insurance_relief_offsets_some_tax():
    """Medical-insurance BIK is taxed but the 20% relief credit reduces income
    tax vs an equivalent non-relief benefit of the same value."""
    med = BenefitInput(
        id=1, person_id=1, kind="medical_insurance", name="VHI",
        start_year=2026, end_year=None, amount=2_000, relief_adults=1,
    )
    other = BenefitInput(
        id=1, person_id=1, kind="other", name="Perk",
        start_year=2026, end_year=None, amount=2_000,
    )
    med_row = simulate(_plan_with_benefit(med))[0]
    other_row = simulate(_plan_with_benefit(other))[0]
    # Same taxable BIK value, but medical insurance gets €200 relief (20% of the
    # €1,000 cap), so its income tax is exactly €200 lower.
    assert abs((other_row.income_tax - med_row.income_tax) - 200.0) < 1


def test_bik_stops_at_retirement():
    """A benefit active past retirement_age contributes nothing once retired."""
    person = PersonInput(
        id=1, name="Worker", dob=date(1960, 1, 1),  # 66 in 2026 → retired
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    benefit = BenefitInput(
        id=1, person_id=1, kind="other", name="Perk",
        start_year=2026, end_year=None, amount=5_000,
    )
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[person], incomes=[], expenses=[], assets=[],
        benefits=[benefit],
        assumptions=AssumptionsInput(inflation_rate=0.0, state_pension_escalation_rate=0.0),
    )
    rows = simulate(plan)
    assert rows[0].benefits_in_kind_total == 0.0


def test_bik_escalates():
    benefit = BenefitInput(
        id=1, person_id=1, kind="other", name="Perk",
        start_year=2026, end_year=None, amount=1_000, escalation_rate=0.10,
    )
    person = PersonInput(
        id=1, name="Worker", dob=date(1985, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    plan = PlanInput(
        base_year=2026, projection_years=3,
        people=[person], incomes=[], expenses=[], assets=[],
        benefits=[benefit],
        assumptions=AssumptionsInput(inflation_rate=0.0, state_pension_escalation_rate=0.0),
    )
    rows = simulate(plan)
    assert abs(rows[0].benefits_in_kind_total - 1_000) < 1
    assert abs(rows[2].benefits_in_kind_total - 1_000 * 1.10 ** 2) < 1


# --------------------------------------------------------------------------
# CRUD + projection API
# --------------------------------------------------------------------------


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


def _seed_plan(client: TestClient) -> tuple[int, int]:
    plan_id = client.post(
        "/api/plans", json={"name": "BIK plan", "base_year": 2026, "projection_years": 1}
    ).json()["id"]
    client.post(
        f"/api/plans/{plan_id}/people",
        json={"name": "Worker", "dob": "1985-01-01", "is_primary": True,
              "life_expectancy": 90, "retirement_age": 66},
    )
    person_id = client.get(f"/api/plans/{plan_id}/people").json()[0]["id"]
    client.post(
        f"/api/people/{person_id}/income",
        json={"kind": "employment", "name": "Job", "gross_amount": 60_000,
              "start_year": 2026, "end_year": None},
    )
    return plan_id, person_id


def test_benefit_crud_and_projection_roundtrip():
    user = _ensure_user("bik-uid", "bik@example.com")
    with TestClient(app) as client, _as_user(user.firebase_uid, user.email or ""):
        plan_id, person_id = _seed_plan(client)

        base = client.get(f"/api/plans/{plan_id}/projection").json()
        base_tax = base["years"][0]["total_tax"]

        r = client.post(
            f"/api/plans/{plan_id}/benefits",
            json={"person_id": person_id, "kind": "medical_insurance", "name": "VHI",
                  "start_year": 2026, "end_year": None, "amount": 2_000, "relief_adults": 1},
        )
        assert r.status_code == 201
        benefit_id = r.json()["id"]

        listed = client.get(f"/api/plans/{plan_id}/benefits").json()
        assert len(listed) == 1 and listed[0]["kind"] == "medical_insurance"

        after = client.get(f"/api/plans/{plan_id}/projection").json()
        year0 = after["years"][0]
        assert abs(year0["benefits_in_kind_total"] - 2_000) < 1
        assert year0["total_tax"] > base_tax  # BIK raised tax

        # Update then delete.
        client.patch(f"/api/benefits/{benefit_id}", json={"amount": 3_000})
        assert client.get(f"/api/plans/{plan_id}/benefits").json()[0]["amount"] == 3_000
        assert client.delete(f"/api/benefits/{benefit_id}").status_code == 204
        assert client.get(f"/api/plans/{plan_id}/benefits").json() == []


def test_benefit_rejects_person_from_other_plan():
    user = _ensure_user("bik2-uid", "bik2@example.com")
    with TestClient(app) as client, _as_user(user.firebase_uid, user.email or ""):
        plan_id, person_id = _seed_plan(client)
        other_plan_id, _ = _seed_plan(client)
        r = client.post(
            f"/api/plans/{other_plan_id}/benefits",
            json={"person_id": person_id, "kind": "other", "name": "X",
                  "start_year": 2026, "end_year": None, "amount": 1_000},
        )
        assert r.status_code == 422
