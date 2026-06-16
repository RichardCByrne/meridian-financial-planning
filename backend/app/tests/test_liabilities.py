"""Liabilities: mortgage/loan amortisation, overpayment, debt-service flow."""

from datetime import date

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    LiabilityInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _person() -> PersonInput:
    return PersonInput(id=1, name="Aoife", dob=date(1990, 1, 1), is_primary=True, life_expectancy=90)


def test_mortgage_amortisation_zero_rate_is_straight_line():
    """0% mortgage: 240k over 240 months = 1000/mo = 12k/yr. Balance falls by 12k."""
    plan = PlanInput(
        base_year=2026,
        projection_years=3,
        people=[_person()],
        incomes=[],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=100_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=240_000.0,
                interest_rate=0.0, term_months=240, start_year=2026, monthly_payment=1_000.0,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    rows = simulate(plan)
    assert abs(rows[0].liability_balances[1] - 228_000.0) < 0.5
    assert abs(rows[1].liability_balances[1] - 216_000.0) < 0.5
    assert abs(rows[0].expenses_by_category["debt_service"] - 12_000.0) < 0.5


def test_mortgage_with_interest_amortises_correctly():
    """Standard 200k @ 4% / 25y mortgage. First-year balance well known."""
    # Standard payment for 200k @ 4%/25y ≈ 1,055.67
    payment = 200_000 * (0.04 / 12) / (1 - (1 + 0.04 / 12) ** -300)
    plan = PlanInput(
        base_year=2026,
        projection_years=2,
        people=[_person()],
        incomes=[],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=20_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment,
            )
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # After 12 payments, balance ≈ 195,245 (closed-form amortisation).
    assert 195_000 < rows[0].liability_balances[1] < 195_500
    assert rows[0].debt_outstanding == rows[0].liability_balances[1]
    # Net worth subtracts debt.
    assert rows[0].net_worth < rows[0].asset_balances[1]


def test_overpayment_shortens_loan_and_reduces_balance():
    """€200/mo extra capital paydown gets the balance lower year-by-year vs zero overpayment."""
    payment = 200_000 * (0.04 / 12) / (1 - (1 + 0.04 / 12) ** -300)
    base_plan = PlanInput(
        base_year=2026, projection_years=5,
        people=[_person()], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=100_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    overpay_plan = PlanInput(
        base_year=2026, projection_years=5,
        people=[_person()], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=100_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment, monthly_overpayment=200.0,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    base_rows = simulate(base_plan)
    over_rows = simulate(overpay_plan)
    # Year-1 balance must be lower with overpayment.
    assert over_rows[0].liability_balances[1] < base_rows[0].liability_balances[1]
    # Approx €200/mo × 12 = €2,400 extra capital paid in year 1 (compounding effect
    # rounds it up slightly via reduced interest).
    diff = base_rows[0].liability_balances[1] - over_rows[0].liability_balances[1]
    assert 2_400 < diff < 2_500
    # Debt service line item rises by the overpayment amount.
    assert (
        over_rows[0].expenses_by_category["debt_service"]
        - base_rows[0].expenses_by_category["debt_service"]
    ) == 200 * 12


def test_negative_overpayment_clamped_to_zero():
    """Negative monthly_overpayment must not extend the loan or grow the balance."""
    payment = 200_000 * (0.04 / 12) / (1 - (1 + 0.04 / 12) ** -300)
    base_plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[_person()], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=50_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    neg_plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[_person()], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=50_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment, monthly_overpayment=-100.0,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    base_rows = simulate(base_plan)
    neg_rows = simulate(neg_plan)
    assert abs(neg_rows[0].liability_balances[1] - base_rows[0].liability_balances[1]) < 0.5
