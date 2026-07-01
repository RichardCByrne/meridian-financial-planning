"""Simulator behavioural edge cases.

Targets the conditional branches in `engine/simulator.py` that only fire under
specific plan states and were previously unexercised: AVC pension top-ups,
the three asset-contribution modes + their time window, mid-year loan payoff,
self-employment income, inactive benefit/expense windows, and defined-benefit
pensions in a multi-person plan.

Distinct from `test_engine_edge_cases.py` (pure input-validation / NaN guards)
and `test_simulator.py` (the happy-path year-by-year integration).
"""

from datetime import date

import pytest

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    BenefitInput,
    DBPensionInput,
    ExpenseInput,
    IncomeInput,
    LiabilityInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _person(pid: int = 1, name: str = "Aoife", dob: date = date(1990, 1, 1)) -> PersonInput:
    return PersonInput(id=pid, name=name, dob=dob, is_primary=(pid == 1), life_expectancy=90)


def _employment(person_id: int = 1, gross: float = 60_000, iid: int = 1) -> IncomeInput:
    return IncomeInput(
        id=iid,
        person_id=person_id,
        kind="employment",
        name="Salary",
        gross_amount=gross,
        start_year=2026,
        end_year=None,
        escalation_rate=0.0,
        pays_prsi=True,
        pays_usc=True,
    )


def _plan(**overrides) -> PlanInput:
    base = dict(
        base_year=2026,
        projection_years=3,
        people=[_person()],
        incomes=[_employment()],
        expenses=[],
        assets=[],
        assumptions=AssumptionsInput(),
    )
    base.update(overrides)
    return PlanInput(**base)


# ----- AVC pension top-ups (avc_annual / avc_pct_of_gross) -----


def test_avc_annual_tops_up_pension_wrapper():
    """A PRSA with avc_annual set contributes on top of any employee %,
    capped by the age-based relievable cap (20% of €60k = €12k here)."""
    prsa = AssetInput(
        id=10, name="PRSA", kind="prsa", value=0.0, growth_rate=0.0, cost_basis=0.0,
        owner_person_id=1, avc_annual=5_000,
    )
    rows = simulate(_plan(assets=[prsa]))
    # Only source of contribution is the €5k AVC.
    assert rows[0].pension_contributions == pytest.approx(5_000.0)
    # It lands in the wrapper balance (growth 0, so exactly the contribution).
    assert rows[0].asset_balances[10] == pytest.approx(5_000.0)


def test_avc_pct_of_gross_is_capped_by_age_band():
    """avc_pct_of_gross of a high fraction is clamped to the remaining
    relievable cap (20% of €60k = €12k for a 36-year-old)."""
    prsa = AssetInput(
        id=11, name="PRSA", kind="prsa", value=0.0, growth_rate=0.0, cost_basis=0.0,
        owner_person_id=1, avc_pct_of_gross=0.90,
    )
    rows = simulate(_plan(assets=[prsa]))
    assert rows[0].pension_contributions == pytest.approx(12_000.0)


# ----- Asset contributions: fixed / % net / % gross / window -----


def test_fixed_annual_asset_contribution():
    inv = AssetInput(
        id=20, name="Fund", kind="investment_unwrapped", value=0.0, growth_rate=0.0,
        cost_basis=0.0, owner_person_id=1, annual_contribution=3_000,
    )
    rows = simulate(_plan(assets=[inv]))
    assert rows[0].asset_contributions == pytest.approx(3_000.0)
    assert rows[0].asset_balances[20] == pytest.approx(3_000.0)


def test_asset_contribution_pct_of_net_income():
    inv = AssetInput(
        id=21, name="Fund", kind="investment_unwrapped", value=0.0, growth_rate=0.0,
        cost_basis=0.0, owner_person_id=1, contribution_pct_of_net_income=0.10,
    )
    rows = simulate(_plan(assets=[inv]))
    net = rows[0].persons[0].net_income
    assert net > 0
    assert rows[0].asset_contributions == pytest.approx(0.10 * net, abs=0.02)


def test_asset_contribution_pct_of_gross_income_household_when_unowned():
    """owner_person_id=None grades the % against household gross, not one person."""
    inv = AssetInput(
        id=22, name="Fund", kind="investment_unwrapped", value=0.0, growth_rate=0.0,
        cost_basis=0.0, owner_person_id=None, contribution_pct_of_gross_income=0.10,
    )
    rows = simulate(_plan(assets=[inv]))
    # Household gross earned = €60k → 10% = €6k.
    assert rows[0].asset_contributions == pytest.approx(6_000.0)


def test_asset_contribution_window_gates_years():
    inv = AssetInput(
        id=23, name="Fund", kind="investment_unwrapped", value=0.0, growth_rate=0.0,
        cost_basis=0.0, owner_person_id=1, annual_contribution=3_000,
        contribution_start_year=2028,
    )
    rows = simulate(_plan(assets=[inv]))
    assert rows[0].asset_contributions == 0.0  # 2026 — before window
    assert rows[1].asset_contributions == 0.0  # 2027 — before window
    assert rows[2].asset_contributions == pytest.approx(3_000.0)  # 2028 — in window


# ----- Liability amortisation: mid-year payoff via overpayment -----


def test_loan_pays_off_within_the_year_with_overpayment():
    """A small loan with a large overpayment clears mid-year, exercising the
    principal>=balance payoff branch and the already-zero early return."""
    loan = LiabilityInput(
        id=30, name="Car loan", kind="personal", principal=5_000, interest_rate=0.0,
        term_months=360, start_year=2026, monthly_payment=500, monthly_overpayment=600,
    )
    rows = simulate(_plan(liabilities=[loan]))
    assert rows[0].debt_outstanding == 0.0
    assert 30 not in rows[0].liability_balances


# ----- Self-employment income -----


def test_self_employment_income_is_projected():
    inc = IncomeInput(
        id=2, person_id=1, kind="self_employment", name="Consulting",
        gross_amount=40_000, start_year=2026, end_year=None, escalation_rate=0.0,
        pays_prsi=True, pays_usc=True,
    )
    rows = simulate(_plan(incomes=[inc]))
    assert rows[0].gross_income_total >= 40_000
    assert rows[0].income_by_kind.get("self_employment", 0.0) == pytest.approx(40_000.0)


# ----- Inactive benefit / expense windows -----


def test_out_of_window_benefits_and_expenses_are_skipped():
    past_benefit = BenefitInput(
        id=40, person_id=1, kind="medical_insurance", name="Old VHI",
        start_year=2020, end_year=2021, amount=1_000,
    )
    future_benefit = BenefitInput(
        id=41, person_id=1, kind="medical_insurance", name="Future VHI",
        start_year=2030, end_year=None, amount=1_000,
    )
    future_expense = ExpenseInput(
        id=50, name="Wedding", category="basic", amount=20_000, start_year=2030,
        end_year=None, escalation_rate=0.0,
    )
    past_expense = ExpenseInput(
        id=51, name="Old subscription", category="basic", amount=500, start_year=2018,
        end_year=2020, escalation_rate=0.0,
    )
    rows = simulate(
        _plan(benefits=[past_benefit, future_benefit], expenses=[future_expense, past_expense])
    )
    # Neither benefit is active in 2026 → no notional pay charged.
    assert rows[0].benefits_in_kind_total == 0.0
    # Neither expense is active in 2026.
    assert rows[0].expenses_total == 0.0


# ----- Defined-benefit pension in a multi-person plan -----


def test_db_pension_only_pays_the_matching_person():
    """Two people, DB pension attached to person 2 only. Person 1's iteration
    must skip it, and person 2 receives the guaranteed income at retirement."""
    p1 = _person(1, "Aoife", date(1990, 1, 1))
    p2 = _person(2, "Sean", date(1961, 1, 1))  # turns 65 in 2026
    dbp = DBPensionInput(
        id=60, person_id=2, name="Public service", accrual_rate=0.0125,
        service_years=40, final_salary=50_000, revaluation_rate=0.0,
        normal_retirement_age=65,
    )
    rows = simulate(
        _plan(people=[p1, p2], incomes=[_employment(person_id=1)], db_pensions=[dbp])
    )
    # 0.0125 × 40 × 50_000 = €25k guaranteed from 2026.
    assert rows[0].db_pension_total == pytest.approx(25_000.0)
