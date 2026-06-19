"""Pension: contributions, retirement crystallisation, lump sum, ARF/annuity/
taxable-cash options, imputed + voluntary ARF drawdown, employer contributions,
and income behaviour at retirement."""

from datetime import date

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _employee(retirement_age: int | None = 65) -> PersonInput:
    """Single PAYE employee, born 1985-01-01 (age 41 in base_year 2026)."""
    return PersonInput(
        id=1, name="Liam", dob=date(1985, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=retirement_age,
    )


def _salary(pct: float = 0.0, gross: float = 80_000) -> IncomeInput:
    return IncomeInput(
        id=1, person_id=1, kind="employment", name="Salary",
        gross_amount=gross, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        pension_contribution_pct=pct,
    )


def test_pension_contribution_not_double_counted_in_surplus():
    """Regression: the pension contribution must reduce the surplus exactly once.

    Previously `gross_income` was reported net of the contribution AND the cash
    flow subtracted it again, understating the surplus by the contribution.
    """
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[_employee()],
        incomes=[_salary(pct=0.10, gross=100_000)],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=0.0, growth_rate=0.0, cost_basis=0.0)],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )
    row = simulate(plan)[0]
    # True gross is reported (not the IT-taxable base net of the contribution).
    assert sum(pr.gross_income for pr in row.persons) == 100_000.0
    assert row.pension_contributions == 10_000.0
    # net_income is gross − tax (before the contribution is diverted); surplus is
    # net minus the contribution (once) and expenses (zero here).
    assert abs(row.surplus_or_shortfall - (row.net_income_total - 10_000.0)) < 0.01


# --- Contributions reduce taxable income and grow the wrapper ----------------


def test_pension_contribution_grows_implicit_prsa():
    """No PRSA asset declared. Engine creates implicit one and routes contributions there."""
    plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[_employee()],
        incomes=[_salary(pct=0.20)],
        expenses=[],
        assets=[],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # Year 0: 20% × 80k = 16k contribution into implicit PRSA. Asset balance grows
    # at default_growth_rate (5%). Implicit PRSA id = -1001.
    bal = rows[0].asset_balances.get(-1001, 0)
    # Pension wrapper grew at 5% on 0 → 0, then +16k contribution at end-of-year
    # in our model = 16k. Year 1: 16k × 1.05 + 16k = 32.8k.
    assert abs(bal - 16_000) < 100
    assert abs(rows[1].asset_balances.get(-1001, 0) - 32_800) < 200


def test_pension_contribution_reduces_taxable_income():
    """20% × 80k = 16k contribution should drop taxable income from 80k to 64k for IT."""
    plan_no_pension = PlanInput(
        base_year=2026, projection_years=1,
        people=[_employee()], incomes=[_salary(pct=0.0)],
        expenses=[], assets=[],
        assumptions=AssumptionsInput(),
    )
    plan_with_pension = PlanInput(
        base_year=2026, projection_years=1,
        people=[_employee()], incomes=[_salary(pct=0.20)],
        expenses=[], assets=[],
        assumptions=AssumptionsInput(),
    )
    no_pen = simulate(plan_no_pension)[0]
    with_pen = simulate(plan_with_pension)[0]
    # IT savings ≈ 16k × 40% (above SRCO at 80k) = €6,400 (approx).
    saved = no_pen.income_tax - with_pen.income_tax
    assert 6_000 < saved < 6_800


def test_age_cap_limits_contribution():
    """Young person (age 41 → 25% cap) requesting 40% gets only 25%."""
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[_employee()], incomes=[_salary(pct=0.40)],
        expenses=[], assets=[],
        assumptions=AssumptionsInput(),
    )
    row = simulate(plan)[0]
    # 25% × 80k = 20k contribution, not 32k.
    assert abs(row.asset_balances.get(-1001, 0) - 20_000) < 100
    assert abs(row.pension_contributions - 20_000) < 100


# --- Retirement event --------------------------------------------------------


def test_retirement_creates_lump_sum_and_arf():
    """Person retires year 1. Pre-existing PRSA worth 200k → 50k lump (tax-free) + 150k ARF."""
    person = PersonInput(
        id=1, name="Maeve", dob=date(1961, 1, 1),  # age 65 in 2026
        is_primary=True, life_expectancy=90, retirement_age=66,  # retires in 2027
    )
    plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[person],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=10_000, growth_rate=0.0, cost_basis=0.0),
            AssetInput(id=2, name="PRSA", kind="prsa", value=200_000, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # Year 0 (2026): age 65, no retirement yet, PRSA still ~200k.
    assert rows[0].pension_lump_sum == 0
    assert rows[0].asset_balances.get(2, 0) == 200_000
    # Year 1 (2027): age 66, retire. Pot = 200k. Lump sum = 50k, tax = 0 (under 200k).
    # ARF = 150k. PRSA → 0.
    r1 = rows[1]
    assert abs(r1.pension_lump_sum - 50_000) < 1
    assert r1.pension_lump_sum_tax == 0
    # PRSA wiped, ARF created at id -2001.
    assert r1.asset_balances.get(2, 0) == 0
    assert abs(r1.asset_balances.get(-2001, 0) - 150_000 * (1 - 0.04)) < 5_000  # less the imputed drawdown


def test_partial_lump_sum_pct_routes_more_to_arf():
    """lump_sum_pct=0.10 → 10% lump, 90% ARF (vs. default 25/75)."""
    person = PersonInput(
        id=1, name="Niamh", dob=date(1961, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
        lump_sum_pct=0.10,
    )
    plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[person],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=10_000, growth_rate=0.0, cost_basis=0.0),
            AssetInput(id=2, name="PRSA", kind="prsa", value=200_000, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    r1 = rows[1]
    # 200k pot * 10% = 20k lump, 180k → ARF. Lump under 200k threshold → tax 0.
    assert abs(r1.pension_lump_sum - 20_000) < 1
    assert r1.pension_lump_sum_tax == 0
    # ARF holds 180k less the year-1 imputed 4% drawdown.
    assert abs(r1.asset_balances.get(-2001, 0) - 180_000 * (1 - 0.04)) < 5_000


def test_lump_sum_pct_clamped_above_25_pct():
    """Out-of-range lump_sum_pct values are clamped to the legal 0–25% range."""
    person = PersonInput(
        id=1, name="Greedy", dob=date(1961, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
        lump_sum_pct=0.50,  # illegal, must clamp to 0.25
    )
    plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[person],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=0, growth_rate=0.0, cost_basis=0.0),
            AssetInput(id=2, name="PRSA", kind="prsa", value=200_000, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    assert abs(rows[1].pension_lump_sum - 50_000) < 1  # 25% of 200k


def test_lump_sum_tax_above_200k_threshold():
    """Pot of 1M → lump sum 250k. Tax = 50k * 20% = 10k."""
    person = PersonInput(
        id=1, name="Padraig", dob=date(1961, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[person],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=0, growth_rate=0.0, cost_basis=0.0),
            AssetInput(id=2, name="PRSA", kind="prsa", value=1_000_000.0, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    r1 = rows[1]
    assert abs(r1.pension_lump_sum - 250_000) < 1
    assert abs(r1.pension_lump_sum_tax - 10_000) < 1


# --- Pension option at retirement (ARF / annuity / taxable lump sum) ---------


def _retiree_with_prsa(pension_option: str, **kwargs) -> PlanInput:
    """Single person, age 65 in 2026, retires 2027, 200k PRSA. State pension
    zeroed so the only post-retirement income is the chosen pension option."""
    person = PersonInput(
        id=1, name="Orla", dob=date(1961, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
        pension_option=pension_option, **kwargs,
    )
    return PlanInput(
        base_year=2026, projection_years=3,
        people=[person], incomes=[], expenses=[],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=10_000, growth_rate=0.0, cost_basis=0.0),
            AssetInput(id=2, name="PRSA", kind="prsa", value=200_000, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        assumptions=AssumptionsInput(state_pension_annual_amount=0),
    )


def test_annuity_option_pays_level_income_and_creates_no_arf():
    """annuity option: 150k remainder × 4% = 6k/yr level income, no ARF, pot leaves estate."""
    rows = simulate(_retiree_with_prsa("annuity", annuity_rate=0.04))
    # Pre-retirement year: no annuity.
    assert rows[0].income_by_kind.get("annuity", 0) == 0
    # Retirement year 2027 and the year after: 6k annuity each.
    assert abs(rows[1].income_by_kind.get("annuity", 0) - 6_000) < 1
    assert abs(rows[2].income_by_kind.get("annuity", 0) - 6_000) < 1
    # No ARF wrapper created (ARF synthetic id is -2001).
    assert rows[1].asset_balances.get(-2001, 0) == 0
    # No ARF imputed drawdown.
    assert rows[1].arf_drawdowns == 0


def test_taxable_lump_sum_option_charges_remainder_as_income_once():
    """taxable_lump_sum: whole 150k remainder taxed as income in the retirement year only."""
    rows = simulate(_retiree_with_prsa("taxable_lump_sum"))
    assert rows[0].income_by_kind.get("pension_taxable_cash", 0) == 0
    # 200k pot, 25% lump = 50k, remainder 150k taken as taxable cash in 2027.
    assert abs(rows[1].income_by_kind.get("pension_taxable_cash", 0) - 150_000) < 1
    # One-shot: not repeated next year.
    assert rows[2].income_by_kind.get("pension_taxable_cash", 0) == 0
    # No ARF created.
    assert rows[1].asset_balances.get(-2001, 0) == 0
    # Big income → meaningful income tax that year.
    assert rows[1].income_tax > 0


def test_arf_option_is_the_default_and_creates_an_arf():
    """Default (no pension_option) and explicit 'arf' both route the remainder to an ARF."""
    default_rows = simulate(_retiree_with_prsa("arf"))
    # ARF wrapper exists post-retirement, ~150k less the 4% imputed drawdown.
    assert default_rows[1].asset_balances.get(-2001, 0) > 100_000
    assert default_rows[1].arf_drawdowns > 0
    assert default_rows[1].income_by_kind.get("annuity", 0) == 0


# --- ARF imputed distribution ------------------------------------------------


def test_arf_drawdown_at_4_percent_age_60_to_69():
    """Pre-existing ARF at age 67 → 4% mandatory drawdown each year."""
    person = PersonInput(
        id=1, name="Niamh", dob=date(1959, 1, 1),  # age 67 in 2026
        is_primary=True, life_expectancy=90, retirement_age=60,
    )
    plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[person],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="ARF", kind="arf", value=500_000, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        assumptions=AssumptionsInput(state_pension_annual_amount=0),  # isolate ARF income
    )
    rows = simulate(plan)
    r0 = rows[0]
    # 4% of 500k = 20k drawdown, ARF → 480k.
    assert abs(r0.arf_drawdowns - 20_000) < 1
    assert abs(r0.asset_balances[1] - 480_000) < 1
    # Drawdown shows up as gross income for the year (USC always bites; IT may
    # be fully covered by personal + PAYE credits at this level).
    assert abs(r0.gross_income_total - 20_000) < 1
    assert r0.usc > 0


def test_arf_drawdown_jumps_to_5_percent_at_70():
    person = PersonInput(
        id=1, name="Sean", dob=date(1956, 1, 1),  # age 70 in 2026
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[person],
        incomes=[],
        expenses=[],
        assets=[
            AssetInput(id=1, name="ARF", kind="arf", value=300_000, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        assumptions=AssumptionsInput(state_pension_annual_amount=0),
    )
    rows = simulate(plan)
    # 5% of 300k = 15k.
    assert abs(rows[0].arf_drawdowns - 15_000) < 1


# --- Employer pension contribution ------------------------------------------


def test_employer_contribution_lands_in_wrapper_without_reducing_taxable_income():
    """Employer 8% on €80k salary = €6,400 into PRSA. Employee taxable income unchanged."""
    income = IncomeInput(
        id=1, person_id=1, kind="employment", name="Salary",
        gross_amount=80_000, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        pension_contribution_pct=0.0,
        employer_pension_contribution_pct=0.08,
    )
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[_employee()], incomes=[income], expenses=[], assets=[],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    r = rows[0]
    # Taxable income still 80k (employer contribution is not a deduction).
    assert abs(r.gross_income_total - 80_000) < 1
    # Wrapper holds 6,400 grown at 5%: rounded check on PRSA wrapper balance.
    prsa_bal = r.asset_balances.get(-1001, 0)
    assert 6_300 < prsa_bal < 6_500
    # Employee pension_contributions field is 0; employer field is 6,400.
    assert r.pension_contributions == 0
    assert abs(r.employer_pension_contributions - 6_400) < 1


def test_employer_contribution_does_not_reduce_household_cash_flow():
    """Employee owns the salary cash; employer contribution should not be subtracted."""
    income = IncomeInput(
        id=1, person_id=1, kind="employment", name="Salary",
        gross_amount=80_000, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        pension_contribution_pct=0.0,
        employer_pension_contribution_pct=0.10,
    )
    plan_with = PlanInput(
        base_year=2026, projection_years=1,
        people=[_employee()], incomes=[income], expenses=[], assets=[],
        assumptions=AssumptionsInput(),
    )
    plan_without = PlanInput(
        base_year=2026, projection_years=1,
        people=[_employee()], incomes=[_salary(pct=0.0)], expenses=[], assets=[],
        assumptions=AssumptionsInput(),
    )
    cash_with = simulate(plan_with)[0].surplus_or_shortfall
    cash_without = simulate(plan_without)[0].surplus_or_shortfall
    # Employer contribution is invisible to household cash flow.
    assert abs(cash_with - cash_without) < 1


# --- Income behaviour at retirement -----------------------------------------


def test_employment_income_stops_at_retirement_even_with_open_end_year():
    """Open-ended employment income must not pay past retirement_age."""
    person = PersonInput(
        id=1, name="Sinead", dob=date(1961, 1, 1),  # 65 in 2026
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    salary = IncomeInput(
        id=1, person_id=1, kind="employment", name="Salary",
        gross_amount=80_000, start_year=2026, end_year=None,  # open
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        pension_contribution_pct=0.0,
    )
    plan = PlanInput(
        base_year=2026, projection_years=3,
        people=[person], incomes=[salary], expenses=[], assets=[],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # Year 0 (2026): age 65 — salary pays.
    assert rows[0].income_by_kind.get("employment", 0) == 80_000
    # Year 1 (2027): age 66 — retired, salary stops despite no end_year.
    assert rows[1].income_by_kind.get("employment", 0) == 0
    # Year 2 (2028): still no employment income.
    assert rows[2].income_by_kind.get("employment", 0) == 0


def test_rental_income_continues_past_retirement():
    """Rental is passive — it must keep paying after retirement."""
    person = PersonInput(
        id=1, name="Brid", dob=date(1961, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    rental = IncomeInput(
        id=1, person_id=1, kind="rental", name="Rental",
        gross_amount=12_000, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=False, pays_usc=True,
        pension_contribution_pct=0.0,
    )
    plan = PlanInput(
        base_year=2026, projection_years=3,
        people=[person], incomes=[rental], expenses=[], assets=[],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    assert rows[0].income_by_kind.get("rental", 0) == 12_000
    assert rows[1].income_by_kind.get("rental", 0) == 12_000
    assert rows[2].income_by_kind.get("rental", 0) == 12_000


# --- Voluntary ARF drawdown rate --------------------------------------------


def _retired_with_arf(target_pct: float | None, value: float = 200_000):
    person = PersonInput(
        id=1, name="ARF target", dob=date(1960, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
        arf_target_drawdown_pct=target_pct,
    )
    plan = PlanInput(
        base_year=2026, projection_years=1,
        people=[person], incomes=[], expenses=[],
        assets=[
            AssetInput(id=1, name="Cash", kind="cash", value=0, growth_rate=0.0, cost_basis=0.0),
            AssetInput(id=2, name="ARF", kind="arf", value=value, growth_rate=0.0,
                       cost_basis=0.0, owner_person_id=1),
        ],
        assumptions=AssumptionsInput(state_pension_annual_amount=0.0),
    )
    return simulate(plan)


def test_arf_target_drawdown_above_minimum_draws_more():
    """target_pct=0.06 with statutory min 4% → engine draws 6% (12k of 200k)."""
    rows = _retired_with_arf(target_pct=0.06)
    assert abs(rows[0].arf_drawdowns - 12_000) < 1


def test_arf_target_below_minimum_uses_statutory():
    """target_pct=0.02 with statutory min 4% → engine still draws the 4% floor."""
    rows = _retired_with_arf(target_pct=0.02)
    assert abs(rows[0].arf_drawdowns - 8_000) < 1


def test_arf_target_none_preserves_legacy_minimum_only():
    """target_pct=None → statutory minimum applies (4% of 200k = 8k)."""
    rows = _retired_with_arf(target_pct=None)
    assert abs(rows[0].arf_drawdowns - 8_000) < 1
