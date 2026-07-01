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


def test_marriage_year_flips_filing_status_mid_projection():
    """A cohabiting single-earner couple that marries in 2028 keeps the same tax
    in 2026/2027 but switches to the married band (lower income tax) from 2028 on."""
    p1 = PersonInput(id=1, name="Aoife", dob=date(1990, 1, 1), is_primary=True, life_expectancy=90)
    p2 = PersonInput(id=2, name="Conor", dob=date(1992, 1, 1), is_primary=False, life_expectancy=90)
    incomes = [
        IncomeInput(
            id=1, person_id=1, kind="employment", name="A", gross_amount=70_000,
            start_year=2026, end_year=None, escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        ),
    ]
    common = dict(
        base_year=2026, projection_years=5, people=[p1, p2], incomes=incomes,
        expenses=[], assets=[], assumptions=AssumptionsInput(),
    )
    cohab = PlanInput(**common, filing_status="cohabiting")
    marrying = PlanInput(**common, filing_status="cohabiting", marriage_year=2028)

    cohab_rows = simulate(cohab)
    rows = simulate(marrying)

    # Pre-marriage (2026, 2027): identical income tax.
    assert abs(rows[0].income_tax - cohab_rows[0].income_tax) < 0.5
    assert abs(rows[1].income_tax - cohab_rows[1].income_tax) < 0.5
    # From the marriage year (2028) on: married band transfer → lower income tax.
    assert rows[2].income_tax < cohab_rows[2].income_tax
    assert cohab_rows[2].income_tax - rows[2].income_tax > 3_000


def test_marriage_year_no_effect_with_single_person():
    """marriage_year needs two people; a solo plan ignores it."""
    p = _person()
    incomes = [
        IncomeInput(
            id=1, person_id=1, kind="employment", name="A", gross_amount=70_000,
            start_year=2026, end_year=None, escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        ),
    ]
    common = dict(
        base_year=2026, projection_years=3, people=[p], incomes=incomes,
        expenses=[], assets=[], assumptions=AssumptionsInput(),
    )
    base = PlanInput(**common, filing_status="single")
    with_event = PlanInput(**common, filing_status="single", marriage_year=2027)
    assert simulate(with_event)[-1].income_tax == simulate(base)[-1].income_tax


def test_bonus_income_stops_at_retirement_even_with_open_end_year():
    """A bonus (kind='other', is_bonus=True, no end_year) is employment-related,
    so it stops at retirement like salary — unlike a plain passive 'other'
    income which keeps flowing."""
    person = PersonInput(
        id=1, name="Aoife", dob=date(1960, 1, 1), is_primary=True,
        life_expectancy=90, retirement_age=66,
    )
    # base_year 2025: age 65 (working) in 2025, age 66 (retired) in 2026.
    bonus = IncomeInput(
        id=1, person_id=1, kind="other", name="Annual bonus",
        gross_amount=10_000, start_year=2025, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True, is_bonus=True,
    )
    passive = IncomeInput(
        id=2, person_id=1, kind="other", name="Royalties",
        gross_amount=5_000, start_year=2025, end_year=None,
        escalation_rate=0.0, pays_prsi=False, pays_usc=True, is_bonus=False,
    )
    plan = PlanInput(
        base_year=2025, projection_years=2,
        people=[person], incomes=[bonus, passive], expenses=[], assets=[],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # 2025 (working, age 65): both flow → "other" income includes 15k.
    assert abs(rows[0].income_by_kind.get("other", 0) - 15_000) < 1
    # 2026 (retired, age 66): bonus stops, passive royalties continue → 5k.
    assert abs(rows[1].income_by_kind.get("other", 0) - 5_000) < 1


def test_annual_charge_reduces_asset_growth():
    """A product charge is deducted from growth, so the pot compounds at the net
    rate. 6% growth − 1.5% charge = 4.5% net over 3 years."""
    def _plan(charge: float) -> PlanInput:
        return PlanInput(
            base_year=2026,
            projection_years=3,
            people=[_person()],
            incomes=[],
            expenses=[],
            assets=[
                AssetInput(
                    id=1, name="Fund", kind="investment_unwrapped", value=100_000,
                    growth_rate=0.06, cost_basis=100_000.0, annual_charge_pct=charge,
                )
            ],
            assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
        )

    gross = simulate(_plan(0.0))
    net = simulate(_plan(0.015))
    # Charge-free grows at 6%; charged grows at 4.5%.
    assert abs(gross[2].asset_balances[1] - 100_000 * 1.06 ** 3) < 1.0
    assert abs(net[2].asset_balances[1] - 100_000 * 1.045 ** 3) < 1.0
    # And the charge visibly lowers the terminal balance.
    assert net[2].asset_balances[1] < gross[2].asset_balances[1]


def test_annual_charge_exceeding_growth_does_not_go_negative():
    """A charge larger than growth shrinks the pot but never drives it below zero."""
    plan = PlanInput(
        base_year=2026,
        projection_years=2,
        people=[_person()],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(
                id=1, name="Fund", kind="investment_unwrapped", value=10_000,
                growth_rate=0.02, cost_basis=10_000.0, annual_charge_pct=0.10,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )
    rows = simulate(plan)
    # 2% growth − 10% charge = −8% net: balance shrinks but stays positive.
    assert 0.0 < rows[0].asset_balances[1] < 10_000
    assert abs(rows[0].asset_balances[1] - 10_000 * 0.92) < 1.0
