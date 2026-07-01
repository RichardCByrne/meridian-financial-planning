"""Defined-benefit / final-salary pension income: accrual formula, revaluation,
NRA start, PAYE/PRSI-exempt treatment, tax-free lump sum."""

from datetime import date

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    DBPensionInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _person(birth_year: int) -> PersonInput:
    return PersonInput(
        id=1, name="Aoife", dob=date(birth_year, 1, 1), is_primary=True, life_expectancy=95
    )


def _plan(person: PersonInput, dp: DBPensionInput, years: int = 6) -> PlanInput:
    return PlanInput(
        base_year=2026, projection_years=years,
        people=[person], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=0.0, growth_rate=0.0, cost_basis=0.0)],
        db_pensions=[dp],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )


def test_db_pension_pays_from_nra_with_accrual_formula():
    # Born 1961, NRA 65 → starts 2026 (base year). 40/60 × 60,000 = 40,000/yr.
    dp = DBPensionInput(
        id=1, person_id=1, name="Final salary", accrual_rate=1 / 60,
        service_years=40, final_salary=60_000, revaluation_rate=0.0,
        normal_retirement_age=65,
    )
    rows = simulate(_plan(_person(1961), dp))
    assert abs(rows[0].income_by_kind.get("db_pension", 0) - 40_000) < 1
    assert abs(rows[0].db_pension_total - 40_000) < 1
    # PAYE-taxed …
    assert rows[0].income_tax > 0
    # … but PRSI-exempt (only pension income this year).
    assert rows[0].prsi == 0.0


def test_db_pension_absent_before_nra():
    # Born 1970, NRA 65 → starts 2035, outside a 6-year projection.
    dp = DBPensionInput(
        id=1, person_id=1, name="Final salary", accrual_rate=1 / 60,
        service_years=40, final_salary=60_000, normal_retirement_age=65,
    )
    rows = simulate(_plan(_person(1970), dp))
    assert all(r.db_pension_total == 0.0 for r in rows)


def test_db_pension_revaluation_indexes_the_income():
    # Born 1963, NRA 65 → starts 2028 (2 years after base). Base 40,000 revalued
    # at 2%/yr for 2 years = 40,000 × 1.02² = 41,616.
    dp = DBPensionInput(
        id=1, person_id=1, name="Final salary", accrual_rate=1 / 60,
        service_years=40, final_salary=60_000, revaluation_rate=0.02,
        normal_retirement_age=65,
    )
    rows = simulate(_plan(_person(1963), dp))
    assert rows[1].db_pension_total == 0.0  # 2027, before NRA
    assert abs(rows[2].income_by_kind.get("db_pension", 0) - 40_000 * 1.02 ** 2) < 1


def test_db_pension_tax_free_lump_sum_lands_in_cash_at_nra():
    dp = DBPensionInput(
        id=1, person_id=1, name="Final salary", accrual_rate=1 / 60,
        service_years=40, final_salary=60_000, normal_retirement_age=65,
        tax_free_lump_sum=100_000,
    )
    rows = simulate(_plan(_person(1961), dp))
    # Lump sum is capital, tax-free: it swells cash in the NRA year but isn't income.
    assert rows[0].asset_balances[1] >= 100_000
    # Only once — the next year's cash reflects the pension net income, not a second lump.
    assert rows[1].asset_balances[1] - rows[0].asset_balances[1] < 100_000
