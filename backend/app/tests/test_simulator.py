"""Integration tests for the year-by-year simulator."""

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


def _person(pid: int = 1, name: str = "Aoife") -> PersonInput:
    return PersonInput(
        id=pid, name=name, dob=date(1990, 1, 1), is_primary=True, life_expectancy=90
    )


def test_zero_income_zero_expenses_zero_assets_yields_flat_zero():
    plan = PlanInput(
        base_year=2026,
        projection_years=3,
        people=[_person()],
        incomes=[],
        expenses=[],
        assets=[],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    assert len(rows) == 3
    assert all(r.net_worth == 0.0 for r in rows)
    assert all(r.gross_income_total == 0.0 for r in rows)


def test_simple_employee_with_growing_cash():
    """Single PAYE earner, no expenses, income deposits into cash asset."""
    plan = PlanInput(
        base_year=2026,
        projection_years=3,
        people=[_person()],
        incomes=[
            IncomeInput(
                id=1,
                person_id=1,
                kind="employment",
                name="Salary",
                gross_amount=60_000,
                start_year=2026,
                end_year=None,
                escalation_rate=0.0,
                pays_prsi=True,
                pays_usc=True,
            )
        ],
        expenses=[],
        assets=[
            AssetInput(id=1, name="Current account", kind="cash", value=0.0, growth_rate=0.0, cost_basis=0.0)
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )
    rows = simulate(plan)
    # Single PAYE 60k -> net 44,924.68 (PRSI 4.2375% 2026 blend; verified in tax tests)
    assert abs(rows[0].net_income_total - 44_924.68) < 0.05
    # Cash accumulates: yr0 = 44,924.68; yr2 = 134,774.04
    assert abs(rows[0].asset_balances[1] - 44_924.68) < 0.5
    assert abs(rows[2].asset_balances[1] - 134_774.04) < 1.0


def test_expenses_drain_cash_then_signal_shortfall():
    """Expenses exceed income — cash drains, then shortfall recorded."""
    plan = PlanInput(
        base_year=2026,
        projection_years=4,
        people=[_person()],
        incomes=[],  # no income, retirement-like
        expenses=[
            ExpenseInput(
                id=1, name="Living", category="basic", amount=20_000,
                start_year=2026, end_year=None, escalation_rate=0.0,
            )
        ],
        assets=[
            AssetInput(id=1, name="Pot", kind="cash", value=50_000, growth_rate=0.0, cost_basis=0.0)
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    rows = simulate(plan)
    # Year 0: 50k - 20k = 30k cash. Year 1: 30k - 20k = 10k. Year 2: 10k - 20k -> 0 with shortfall.
    assert abs(rows[0].asset_balances[1] - 30_000.0) < 0.5
    assert abs(rows[1].asset_balances[1] - 10_000.0) < 0.5
    assert rows[2].asset_balances.get(1, 0.0) == 0.0
    assert any("Shortfall" in n for n in rows[2].notes)


def test_liquidation_order_drains_cash_before_investment():
    plan = PlanInput(
        base_year=2026,
        projection_years=2,
        people=[_person()],
        incomes=[],
        expenses=[
            ExpenseInput(id=1, name="Big", category="basic", amount=15_000,
                         start_year=2026, end_year=None, escalation_rate=0.0)
        ],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=10_000, growth_rate=0.0, cost_basis=0.0),
            # cost_basis == value -> zero gain, no exit tax, simple liquidation maths.
            AssetInput(id=2, name="ETF", kind="etf_fund", value=20_000, growth_rate=0.0, cost_basis=20_000.0),
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    rows = simulate(plan)
    # Year 0: cash drained to 0, ETF takes the remaining 5k.
    assert rows[0].asset_balances.get(1, 0.0) == 0.0
    assert abs(rows[0].asset_balances[2] - 15_000.0) < 0.5
    assert rows[0].withdrawals_by_asset.get(1, 0.0) == 10_000.0
    assert rows[0].withdrawals_by_asset.get(2, 0.0) == 5_000.0


def test_income_escalation_compounds_yearly():
    plan = PlanInput(
        base_year=2026,
        projection_years=3,
        people=[_person()],
        incomes=[
            IncomeInput(
                id=1, person_id=1, kind="employment", name="Salary",
                gross_amount=50_000, start_year=2026, end_year=None,
                escalation_rate=0.10, pays_prsi=True, pays_usc=True,
            )
        ],
        expenses=[],
        assets=[],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    assert abs(rows[0].gross_income_total - 50_000.0) < 1
    assert abs(rows[1].gross_income_total - 55_000.0) < 1
    assert abs(rows[2].gross_income_total - 60_500.0) < 1


def test_asset_growth_compounds_when_no_cash_flow():
    plan = PlanInput(
        base_year=2026,
        projection_years=3,
        people=[_person()],
        incomes=[
            IncomeInput(
                id=1, person_id=1, kind="employment", name="S",
                gross_amount=50_000, start_year=2026, end_year=None,
                escalation_rate=0.0, pays_prsi=True, pays_usc=True,
            )
        ],
        expenses=[
            # Match net income exactly so asset just grows.
            ExpenseInput(id=1, name="L", category="basic", amount=37_307.18,
                         start_year=2026, end_year=None, escalation_rate=0.0),
        ],
        assets=[
            AssetInput(id=1, name="ETF", kind="etf_fund", value=10_000, growth_rate=0.10, cost_basis=0.0),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # 10k grown at 10% for 3 years = 13,310. Cash flow ~ 0 each year so no withdrawals or deposits.
    # Allow a small tolerance for the rounded expense match.
    assert abs(rows[2].asset_balances[1] - 13_310.0) < 200.0


def test_single_year_expense_only_fires_once():
    plan = PlanInput(
        base_year=2026,
        projection_years=4,
        people=[_person()],
        incomes=[],
        expenses=[
            ExpenseInput(id=1, name="Wedding", category="single_year",
                         amount=20_000, start_year=2027, end_year=None,
                         escalation_rate=0.0),
        ],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=50_000, growth_rate=0.0, cost_basis=0.0)
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # Year 0 (2026): no spend
    # Year 1 (2027): spend 20k, cash 30k
    # Year 2/3: no spend, cash flat at 30k
    assert abs(rows[0].asset_balances[1] - 50_000.0) < 0.5
    assert abs(rows[1].asset_balances[1] - 30_000.0) < 0.5
    assert abs(rows[2].asset_balances[1] - 30_000.0) < 0.5


def test_cohabiting_filing_status_taxes_each_person_as_single():
    """Two-person plan with filing_status='cohabiting' should NOT use the
    married band (each person assessed individually as Irish Revenue does)."""
    p1 = PersonInput(id=1, name="Aoife", dob=date(1990, 1, 1), is_primary=True, life_expectancy=90)
    p2 = PersonInput(id=2, name="Conor", dob=date(1992, 1, 1), is_primary=False, life_expectancy=90)

    incomes = [
        IncomeInput(
            id=1, person_id=1, kind="employment", name="A", gross_amount=70_000,
            start_year=2026, end_year=None, escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        ),
    ]
    common = dict(
        base_year=2026, projection_years=1, people=[p1, p2], incomes=incomes,
        expenses=[], assets=[], assumptions=AssumptionsInput(),
    )
    married_plan = PlanInput(**common)  # default → auto → married (legacy heuristic)
    cohab_plan = PlanInput(**common, filing_status="cohabiting")

    married_row = simulate(married_plan)[0]
    cohab_row = simulate(cohab_plan)[0]

    # Cohabiting taxed as single → narrower band → higher income tax than married.
    assert cohab_row.income_tax > married_row.income_tax
    # Ballpark sanity: married @ 70k → IT around €11,400; single → around €15,200.
    assert cohab_row.income_tax - married_row.income_tax > 3_000
