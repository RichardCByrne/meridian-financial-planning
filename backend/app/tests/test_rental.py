"""Rental income taxed on profit: allowable-expenses % and wear-and-tear
capital allowance on furnishings (12.5% straight-line over 8 years)."""

from datetime import date

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _rental(expenses_pct: float = 0.0, furnishings: float = 0.0) -> IncomeInput:
    return IncomeInput(
        id=1, person_id=1, kind="rental", name="BTL rent",
        gross_amount=30_000, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        rental_expenses_pct=expenses_pct, furnishings_value=furnishings,
    )


def _plan(rental: IncomeInput, years: int = 10) -> PlanInput:
    return PlanInput(
        base_year=2026, projection_years=years,
        people=[PersonInput(id=1, name="Landlord", dob=date(1980, 1, 1),
                            is_primary=True, life_expectancy=95)],
        incomes=[rental], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=0.0, growth_rate=0.0, cost_basis=0.0)],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )


def test_rental_no_deductions_taxes_gross():
    rows = simulate(_plan(_rental()))
    assert abs(rows[0].income_by_kind.get("rental", 0) - 30_000) < 1


def test_rental_expenses_reduce_taxable_profit_and_tax():
    gross = simulate(_plan(_rental()))[0]
    netted = simulate(_plan(_rental(expenses_pct=0.20)))[0]
    # 20% expenses → taxable rental 24,000.
    assert abs(netted.income_by_kind.get("rental", 0) - 24_000) < 1
    # Less taxable income → less income tax.
    assert netted.income_tax < gross.income_tax


def test_wear_and_tear_allowance_reduces_profit_for_eight_years_then_stops():
    rows = simulate(_plan(_rental(expenses_pct=0.20, furnishings=8_000)))
    # Years 0–7 (let < 8): profit = 30,000 − 6,000 − (8,000×12.5% = 1,000) = 23,000.
    assert abs(rows[0].income_by_kind.get("rental", 0) - 23_000) < 1
    assert abs(rows[7].income_by_kind.get("rental", 0) - 23_000) < 1
    # Year 8 (let == 8): wear-and-tear exhausted → 30,000 − 6,000 = 24,000.
    assert abs(rows[8].income_by_kind.get("rental", 0) - 24_000) < 1


def test_rental_expenses_ignored_for_non_rental_kind():
    """rental_expenses_pct set on an employment row must not deduct anything."""
    emp = IncomeInput(
        id=1, person_id=1, kind="employment", name="Salary",
        gross_amount=50_000, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        rental_expenses_pct=0.50, furnishings_value=10_000,
    )
    rows = simulate(_plan(emp))
    assert abs(rows[0].income_by_kind.get("employment", 0) - 50_000) < 1
