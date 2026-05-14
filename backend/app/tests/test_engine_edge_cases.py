"""Engine edge-case tests (QA_FINDINGS TG1–TG3).

Validates the pure-function simulator against pathological inputs that
should either fail loudly (NaN/inf) or degrade gracefully (zero people,
ages past life expectancy). Pure unit tests — no FastAPI/DB.
"""

from datetime import date

import math
import pytest

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    ExpenseInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _baseline_person() -> PersonInput:
    return PersonInput(
        id=1,
        name="Alice",
        dob=date(1985, 1, 1),
        is_primary=True,
        life_expectancy=90,
        retirement_age=66,
    )


def _baseline_plan(**overrides) -> PlanInput:
    plan = PlanInput(
        base_year=2026,
        projection_years=5,
        people=[_baseline_person()],
        incomes=[
            IncomeInput(
                id=1,
                person_id=1,
                kind="employment",
                name="Salary",
                gross_amount=60_000,
                start_year=2026,
                end_year=None,
                escalation_rate=0.03,
                pays_prsi=True,
                pays_usc=True,
            )
        ],
        expenses=[
            ExpenseInput(
                id=1,
                name="Living",
                category="basic",
                amount=30_000,
                start_year=2026,
                end_year=None,
                escalation_rate=0.025,
            )
        ],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=20_000, growth_rate=0.01, cost_basis=0)
        ],
        assumptions=AssumptionsInput(),
    )
    for k, v in overrides.items():
        setattr(plan, k, v)
    return plan


# ---------- TG1: NaN / inf propagation ----------


def test_simulate_rejects_nan_asset_value():
    plan = _baseline_plan()
    plan.assets[0].value = float("nan")
    with pytest.raises(ValueError, match="asset.*value"):
        simulate(plan)


def test_simulate_rejects_inf_income():
    plan = _baseline_plan()
    plan.incomes[0].gross_amount = float("inf")
    with pytest.raises(ValueError, match="income.*gross_amount"):
        simulate(plan)


def test_simulate_rejects_nan_escalation_rate():
    plan = _baseline_plan()
    plan.expenses[0].escalation_rate = float("nan")
    with pytest.raises(ValueError, match="expense.*escalation_rate"):
        simulate(plan)


def test_simulate_rejects_nan_inflation():
    plan = _baseline_plan()
    plan.assumptions = AssumptionsInput(inflation_rate=float("nan"))
    with pytest.raises(ValueError, match="inflation_rate"):
        simulate(plan)


def test_simulate_finite_inputs_produce_finite_outputs():
    """Sanity check the guard didn't break the happy path."""
    rows = simulate(_baseline_plan())
    assert len(rows) == 5
    for r in rows:
        assert math.isfinite(r.net_worth)
        assert math.isfinite(r.total_tax)
        assert math.isfinite(r.expenses_total)


# ---------- TG2: zero-person plans ----------


def test_simulate_with_zero_people_completes():
    """An empty household should produce projection_years rows of zeros, not crash."""
    plan = PlanInput(
        base_year=2026,
        projection_years=3,
        people=[],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="Trust", kind="cash", value=50_000, growth_rate=0.0, cost_basis=0)
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    assert len(rows) == 3
    for r in rows:
        assert r.gross_income_total == 0.0
        assert r.total_tax == 0.0
        assert math.isfinite(r.net_worth)


# ---------- TG3: ages past life expectancy ----------


def test_simulate_handles_age_past_life_expectancy():
    """A person whose age exceeds life_expectancy mid-projection should not
    cause the simulator to crash — they die in-projection (deceased_persons)
    and remaining years still produce finite outputs."""
    person = PersonInput(
        id=1,
        name="Senior",
        dob=date(1940, 1, 1),  # 86 in 2026
        is_primary=True,
        life_expectancy=85,    # already exceeded
        retirement_age=66,
    )
    plan = PlanInput(
        base_year=2026,
        projection_years=5,
        people=[person],
        incomes=[],
        expenses=[
            ExpenseInput(id=1, name="Care", category="basic", amount=20_000,
                         start_year=2026, end_year=None, escalation_rate=0.0)
        ],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=100_000, growth_rate=0.0, cost_basis=0)
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    assert len(rows) == 5
    for r in rows:
        assert math.isfinite(r.net_worth)
