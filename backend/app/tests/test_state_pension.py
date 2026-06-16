"""State pension: auto-injection at pension age, and Total Contributions
Approach scaling by PRSI + HomeCaring weeks."""

from datetime import date

from app.engine.simulator import (
    AssumptionsInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _salary(pct: float = 0.0, gross: float = 80_000) -> IncomeInput:
    return IncomeInput(
        id=1, person_id=1, kind="employment", name="Salary",
        gross_amount=gross, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        pension_contribution_pct=pct,
    )


# --- Auto-injection at state pension age -------------------------------------


def test_state_pension_auto_injects_at_state_pension_age():
    person = PersonInput(
        id=1, name="Eilis", dob=date(1960, 1, 1),  # 66 in 2026
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[person], incomes=[], expenses=[],
        assets=[],
        assumptions=AssumptionsInput(state_pension_annual_amount=15_000.0, inflation_rate=0.0),
    )
    rows = simulate(plan)
    assert abs(rows[0].state_pension_total - 15_000) < 1
    assert rows[0].income_by_kind.get("state_pension", 0) == 15_000


def test_state_pension_does_not_inject_below_eligibility_age():
    person = PersonInput(
        id=1, name="Cara", dob=date(1990, 1, 1),  # 36 in 2026
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[person], incomes=[_salary(pct=0.0)], expenses=[],
        assets=[],
        assumptions=AssumptionsInput(state_pension_annual_amount=15_000.0),
    )
    rows = simulate(plan)
    assert rows[0].state_pension_total == 0


# --- Total Contributions Approach (TCA) -------------------------------------


def test_state_pension_zero_below_qualifying_minimum():
    """Under 520 PRSI weeks (10 years) → no state pension at all."""
    person = PersonInput(
        id=1, name="Rian", dob=date(1960, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
        prsi_weeks_at_base_year=400,  # < 520 minimum
    )
    plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[person], incomes=[], expenses=[], assets=[],
        assumptions=AssumptionsInput(state_pension_annual_amount=15_000.0, inflation_rate=0.0),
    )
    rows = simulate(plan)
    assert rows[0].state_pension_total == 0
    assert rows[1].state_pension_total == 0


def test_state_pension_scales_linearly_above_minimum():
    """1,040 paid weeks (20 years) → 50% of full pension under TCA."""
    person = PersonInput(
        id=1, name="Saoirse", dob=date(1960, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
        prsi_weeks_at_base_year=1040,
    )
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[person], incomes=[], expenses=[], assets=[],
        assumptions=AssumptionsInput(state_pension_annual_amount=15_000.0, inflation_rate=0.0),
    )
    rows = simulate(plan)
    assert abs(rows[0].state_pension_total - 7_500) < 1  # 1040/2080 = 50%


def test_homecaring_credits_fill_the_gap():
    """520 paid + 1,040 HomeCaring = 1,560 / 2,080 → 75% pension."""
    person = PersonInput(
        id=1, name="Niamh", dob=date(1960, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
        prsi_weeks_at_base_year=520,
        homecaring_weeks_at_base_year=1040,
    )
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[person], incomes=[], expenses=[], assets=[],
        assumptions=AssumptionsInput(state_pension_annual_amount=15_000.0, inflation_rate=0.0),
    )
    rows = simulate(plan)
    assert abs(rows[0].state_pension_total - 11_250) < 1  # 1560/2080 = 75%


def test_homecaring_income_marker_credits_years_during_projection():
    """A 'homecaring' income entry credits +52 weeks/yr (capped at 1,040)."""
    person = PersonInput(
        id=1, name="Aoife", dob=date(1965, 1, 1),  # 61 in 2026, retires at 66 in 2031
        is_primary=True, life_expectancy=90, retirement_age=66,
        prsi_weeks_at_base_year=520,
        homecaring_weeks_at_base_year=0,
    )
    homecaring = IncomeInput(
        id=1, person_id=1, kind="homecaring", name="Caring for kids",
        gross_amount=0, start_year=2026, end_year=2030,
        escalation_rate=0.0, pays_prsi=False, pays_usc=False,
        pension_contribution_pct=0.0,
    )
    plan = PlanInput(
        base_year=2026, projection_years=10,
        people=[person], incomes=[homecaring], expenses=[], assets=[],
        assumptions=AssumptionsInput(
            state_pension_annual_amount=15_000.0,
            state_pension_escalation_rate=0.0,
            inflation_rate=0.0,
        ),
    )
    rows = simulate(plan)
    # By state pension age (2031), accrued: 520 paid + 5*52 = 260 HomeCaring
    # → 780/2080 = 37.5% of 15,000 = 5,625.
    retirement_row = next(r for r in rows if r.year == 2031)
    assert abs(retirement_row.state_pension_total - 5_625) < 1
    # HomeCaring marker contributes zero to gross income.
    assert retirement_row.income_by_kind.get("homecaring", 0) == 0


def test_state_pension_full_with_default_seed():
    """Default prsi_weeks_at_base_year=2080 → 100% of full state pension (legacy behaviour)."""
    person = PersonInput(
        id=1, name="Eilis", dob=date(1960, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[person], incomes=[], expenses=[], assets=[],
        assumptions=AssumptionsInput(state_pension_annual_amount=15_000.0, inflation_rate=0.0),
    )
    rows = simulate(plan)
    assert abs(rows[0].state_pension_total - 15_000) < 1
