"""Disposal tax: CGT gross-up on unwrapped sales, ETF exit tax, 8-year deemed disposal."""

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


def _person() -> PersonInput:
    return PersonInput(id=1, name="Aoife", dob=date(1990, 1, 1), is_primary=True, life_expectancy=90)


def test_cgt_gross_up_on_unwrapped_liquidation():
    """Need 5k net from a 10k unwrapped position with 0 cost basis.

    All 5k is gain; CGT at 33% means we must withdraw gross G where
    G - 0.33*G = 5000 → G = 5000/0.67 ≈ 7462.69. Then exemption refunds
    €1,270 * 0.33 = €419.10, leaving net tax ≈ 2042.59."""
    plan = PlanInput(
        base_year=2026,
        projection_years=1,
        people=[_person()],
        incomes=[],
        expenses=[
            ExpenseInput(id=1, name="Trip", category="single_year",
                         amount=5_000, start_year=2026, end_year=None, escalation_rate=0.0),
        ],
        assets=[
            AssetInput(id=1, name="Shares", kind="investment_unwrapped",
                       value=10_000.0, growth_rate=0.0, cost_basis=0.0),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    r = rows[0]
    # Gross withdrawn ≈ 7,462.69 (we need 5k net of CGT on full gain).
    assert abs(r.withdrawals_by_asset[1] - 7_462.69) < 5
    # Investment tax: gross-up tax minus exemption refund.
    # Gross tax = 7462.69 * 0.33 = 2462.69; refund = 1270 * 0.33 = 419.10; net ≈ 2043.59.
    assert 2_000 < r.investment_tax < 2_100
    # Remaining balance ≈ 10000 - 7462.69 = 2,537.31
    assert abs(r.asset_balances[1] - 2_537.31) < 5


def test_no_cgt_when_basis_equals_value():
    """If asset is at cost basis, zero gain → zero tax, gross == net."""
    plan = PlanInput(
        base_year=2026,
        projection_years=1,
        people=[_person()],
        incomes=[],
        expenses=[
            ExpenseInput(id=1, name="Trip", category="single_year",
                         amount=5_000, start_year=2026, end_year=None, escalation_rate=0.0),
        ],
        assets=[
            AssetInput(id=1, name="Shares", kind="investment_unwrapped",
                       value=10_000.0, growth_rate=0.0, cost_basis=10_000.0),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    assert abs(rows[0].withdrawals_by_asset[1] - 5_000.0) < 0.5
    assert rows[0].investment_tax == 0.0


def test_etf_exit_tax_on_disposal():
    """ETF at 41% exit tax: need 5k net from 10k value / 0 basis →
    G - 0.41*G = 5000 → G = 5000/0.59 ≈ 8,474.58. Tax ≈ 3,474.58. No exemption."""
    plan = PlanInput(
        base_year=2026,
        projection_years=1,
        people=[_person()],
        incomes=[],
        expenses=[
            ExpenseInput(id=1, name="Trip", category="single_year",
                         amount=5_000, start_year=2026, end_year=None, escalation_rate=0.0),
        ],
        assets=[
            AssetInput(id=1, name="ETF", kind="etf_fund",
                       value=10_000.0, growth_rate=0.0, cost_basis=0.0),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    r = rows[0]
    assert abs(r.withdrawals_by_asset[1] - 8_474.58) < 5
    assert abs(r.investment_tax - 3_474.58) < 5


def test_etf_deemed_disposal_at_year_8():
    """ETF acquired in 2026 with cost basis = initial value = 10k, growing at
    a flat enough rate. At year 2026+8=2034, deemed disposal triggers tax on
    the unrealised gain accrued over 8 years. After the event basis steps up.
    """
    plan = PlanInput(
        base_year=2026,
        projection_years=10,
        people=[_person()],
        incomes=[
            # Cover normal living so we never have to liquidate the ETF.
            IncomeInput(id=1, person_id=1, kind="employment", name="S",
                        gross_amount=80_000, start_year=2026, end_year=None,
                        escalation_rate=0.0, pays_prsi=True, pays_usc=True),
        ],
        expenses=[
            ExpenseInput(id=1, name="L", category="basic", amount=20_000,
                         start_year=2026, end_year=None, escalation_rate=0.0),
        ],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=10_000, growth_rate=0.0, cost_basis=0.0),
            AssetInput(id=2, name="ETF", kind="etf_fund",
                       value=10_000.0, growth_rate=0.05, cost_basis=10_000.0,
                       acquired_year=2026),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # The 8-year mark is base_year + 8 = 2034 — index 8 in `years` (2026 .. 2035).
    deemed_year = 2034
    deemed_row = next(r for r in rows if r.year == deemed_year)
    # At year 8, ETF value = 10000 * 1.05^9 (8 elapsed full growth steps since
    # we grow at start of each year 2026..2034 inclusive = 9 growth steps).
    # gain ≈ value - 10000; tax ≈ gain * 0.41
    expected_value = 10_000 * (1.05 ** 9)
    expected_gain = expected_value - 10_000
    expected_tax = expected_gain * 0.41
    assert abs(deemed_row.investment_tax - expected_tax) < 50
    assert any("deemed disposal" in n.lower() for n in deemed_row.notes)
    # No deemed disposal in non-trigger years (e.g. year 5).
    other_row = next(r for r in rows if r.year == 2030)
    assert other_row.investment_tax == 0.0


def test_investment_bond_exit_tax_on_disposal():
    """Investment bond shares the ETF regime: 41% exit tax on the realised gain,
    no CGT annual exemption. Need 5k net from 10k / 0 basis → G = 5000/0.59."""
    plan = PlanInput(
        base_year=2026,
        projection_years=1,
        people=[_person()],
        incomes=[],
        expenses=[
            ExpenseInput(id=1, name="Trip", category="single_year",
                         amount=5_000, start_year=2026, end_year=None, escalation_rate=0.0),
        ],
        assets=[
            AssetInput(id=1, name="Bond", kind="investment_bond",
                       value=10_000.0, growth_rate=0.0, cost_basis=0.0),
        ],
        assumptions=AssumptionsInput(),
    )
    r = simulate(plan)[0]
    assert abs(r.withdrawals_by_asset[1] - 8_474.58) < 5
    assert abs(r.investment_tax - 3_474.58) < 5


def test_investment_bond_deemed_disposal_at_year_8():
    plan = PlanInput(
        base_year=2026,
        projection_years=10,
        people=[_person()],
        incomes=[
            IncomeInput(id=1, person_id=1, kind="employment", name="S",
                        gross_amount=80_000, start_year=2026, end_year=None,
                        escalation_rate=0.0, pays_prsi=True, pays_usc=True),
        ],
        expenses=[
            ExpenseInput(id=1, name="L", category="basic", amount=20_000,
                         start_year=2026, end_year=None, escalation_rate=0.0),
        ],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=10_000, growth_rate=0.0, cost_basis=0.0),
            AssetInput(id=2, name="Bond", kind="investment_bond",
                       value=10_000.0, growth_rate=0.05, cost_basis=10_000.0,
                       acquired_year=2026),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    deemed_row = next(r for r in rows if r.year == 2034)
    expected_tax = (10_000 * (1.05 ** 9) - 10_000) * 0.41
    assert abs(deemed_row.investment_tax - expected_tax) < 50
    assert any("deemed disposal" in n.lower() for n in deemed_row.notes)
