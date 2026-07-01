"""Capacity for loss: largest one-off market shock the plan absorbs with no
shortfall."""

from datetime import date

from app.engine.loss_capacity import loss_capacity
from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    ExpenseInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _person() -> PersonInput:
    return PersonInput(id=1, name="P", dob=date(1980, 1, 1), is_primary=True, life_expectancy=95)


def _plan(assets, incomes=None, expense=0.0, years=10) -> PlanInput:
    return PlanInput(
        base_year=2026, projection_years=years,
        people=[_person()], incomes=incomes or [],
        expenses=(
            [ExpenseInput(id=1, name="Living", category="basic", amount=expense,
                          start_year=2026, end_year=None, escalation_rate=0.0)]
            if expense > 0 else []
        ),
        assets=assets,
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )


def test_capacity_is_the_buffer_over_the_need():
    # 200k ETF (no gain → no exit tax), 10k/yr expense for 10y = 100k need, no
    # income. The plan can lose the 100k buffer (50%) before it runs short.
    plan = _plan(
        [AssetInput(id=1, name="ETF", kind="etf_fund", value=200_000,
                    growth_rate=0.0, cost_basis=200_000)],
        expense=10_000,
    )
    r = loss_capacity(plan)
    assert not r.already_short
    assert r.investable_base == 200_000
    assert abs(r.max_absorbable_pct - 0.5) < 0.03
    assert abs(r.max_absorbable_loss - 100_000) < 6_000


def test_already_short_plan_has_zero_capacity():
    # 100k assets, 30k/yr for 10y = 300k need → short even with no shock.
    plan = _plan(
        [AssetInput(id=1, name="ETF", kind="etf_fund", value=100_000,
                    growth_rate=0.0, cost_basis=100_000)],
        expense=30_000,
    )
    r = loss_capacity(plan)
    assert r.already_short
    assert r.max_absorbable_loss == 0.0
    assert r.limiting_year is not None


def test_plan_surviving_total_wipe_has_full_capacity():
    # Income covers expenses; the ETF is surplus, so wiping it changes nothing.
    plan = _plan(
        [AssetInput(id=1, name="ETF", kind="etf_fund", value=100_000,
                    growth_rate=0.0, cost_basis=100_000)],
        incomes=[IncomeInput(id=1, person_id=1, kind="employment", name="Salary",
                             gross_amount=60_000, start_year=2026, end_year=None,
                             escalation_rate=0.0, pays_prsi=True, pays_usc=True)],
        expense=10_000,
    )
    r = loss_capacity(plan)
    assert r.max_absorbable_pct == 1.0
    assert r.max_absorbable_loss == 100_000


def test_no_market_assets_reports_zero_base():
    plan = _plan(
        [AssetInput(id=1, name="Cash", kind="cash", value=200_000, growth_rate=0.0, cost_basis=0)],
        expense=10_000,
    )
    r = loss_capacity(plan)
    assert r.investable_base == 0.0
    assert not r.already_short
    # Sanity: the underlying plan really does survive.
    assert not any(row.had_shortfall for row in simulate(plan))
