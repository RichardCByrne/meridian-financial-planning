"""Needs-vs-wants funding floor: trim discretionary spending to protect
essentials before declaring a shortfall."""

from datetime import date

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    ExpenseInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _plan(trim: bool, cash: float, basic: float, discretionary: float, years: int = 1) -> PlanInput:
    return PlanInput(
        base_year=2026, projection_years=years,
        people=[PersonInput(id=1, name="P", dob=date(1980, 1, 1), is_primary=True, life_expectancy=95)],
        incomes=[],
        expenses=[
            ExpenseInput(id=1, name="Essentials", category="basic", amount=basic,
                         start_year=2026, end_year=None, escalation_rate=0.0),
            ExpenseInput(id=2, name="Nice-to-haves", category="discretionary", amount=discretionary,
                         start_year=2026, end_year=None, escalation_rate=0.0),
        ],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=cash, growth_rate=0.0, cost_basis=0.0)],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
        trim_discretionary_on_shortfall=trim,
    )


def test_off_records_shortfall_without_trimming():
    # 25k cash, 30k spend → 5k unfunded. Off = shortfall, full spend.
    r = simulate(_plan(trim=False, cash=25_000, basic=20_000, discretionary=10_000))[0]
    assert r.had_shortfall
    assert r.discretionary_trimmed == 0.0
    assert abs(r.expenses_total - 30_000) < 0.5


def test_on_trims_discretionary_to_avoid_shortfall():
    r = simulate(_plan(trim=True, cash=25_000, basic=20_000, discretionary=10_000))[0]
    # 5k of wants trimmed → spend 25k, fully funded from cash, no shortfall.
    assert not r.had_shortfall
    assert abs(r.discretionary_trimmed - 5_000) < 0.5
    assert abs(r.expenses_total - 25_000) < 0.5
    assert abs(r.expenses_by_category.get("discretionary", 0) - 5_000) < 0.5


def test_on_still_shortfalls_when_essentials_unaffordable():
    # 20k cash, 30k basic + 5k discretionary. Even trimming all 5k of wants,
    # essentials (30k) outstrip the 20k that can be raised → shortfall.
    r = simulate(_plan(trim=True, cash=20_000, basic=30_000, discretionary=5_000))[0]
    assert r.had_shortfall
    assert abs(r.discretionary_trimmed - 5_000) < 0.5


def test_on_does_not_trim_when_funded():
    # Plenty of cash — no deficit, nothing trimmed.
    r = simulate(_plan(trim=True, cash=100_000, basic=20_000, discretionary=10_000))[0]
    assert not r.had_shortfall
    assert r.discretionary_trimmed == 0.0
    assert abs(r.expenses_total - 30_000) < 0.5
