"""Protection: planned death (death_year) and term-life policies (premiums out,
sum assured in on death within term, cover-gap readout)."""

from datetime import date

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    IncomeInput,
    LiabilityInput,
    LifePolicyInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _person(pid: int = 1, name: str = "Aoife", **kw) -> PersonInput:
    return PersonInput(
        id=pid, name=name, dob=date(1980, 1, 1), is_primary=(pid == 1),
        life_expectancy=90, **kw
    )


def _salary(pid: int = 1) -> IncomeInput:
    return IncomeInput(
        id=pid, person_id=pid, kind="employment", name="Salary",
        gross_amount=60_000, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
    )


def test_death_year_stops_income_early():
    """A person with death_year=2028 earns in 2026/2027 then nothing from 2028."""
    plan = PlanInput(
        base_year=2026, projection_years=5,
        people=[_person(death_year=2028)],
        incomes=[_salary()],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=0.0, growth_rate=0.0, cost_basis=0.0)],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )
    rows = simulate(plan)
    assert rows[0].gross_income_total > 0      # 2026 alive
    assert rows[1].gross_income_total > 0      # 2027 alive
    assert rows[2].gross_income_total == 0.0   # 2028 dead — no income
    assert rows[4].gross_income_total == 0.0
    # The death is recorded in the death year, not at life_expectancy.
    assert any("passes" in n for n in rows[2].notes)


def test_term_policy_premium_drains_cash_while_in_force():
    plan = PlanInput(
        base_year=2026, projection_years=3,
        people=[_person()],
        incomes=[],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=50_000, growth_rate=0.0, cost_basis=0.0)],
        life_policies=[
            LifePolicyInput(
                id=1, person_id=1, name="Term cover", sum_assured=250_000,
                premium_annual=1_000, start_year=2026, end_year=2035,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )
    rows = simulate(plan)
    assert rows[0].protection_premiums_total == 1_000
    assert rows[0].expenses_by_category.get("protection") == 1_000
    # No income, only the premium leaves: 50k → 49k → 48k → 47k.
    assert abs(rows[0].asset_balances[1] - 49_000) < 0.5
    assert abs(rows[2].asset_balances[1] - 47_000) < 0.5
    assert rows[0].life_cover_payout == 0.0


def test_term_policy_pays_out_tax_free_on_death_within_term():
    """Insured dies inside the cover term → sum assured lands in survivors' cash
    tax-free, reported as life_cover_payout that year."""
    plan = PlanInput(
        base_year=2026, projection_years=8,
        people=[_person(death_year=2030), _person(pid=2, name="Conor")],
        incomes=[],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=10_000, growth_rate=0.0, cost_basis=0.0)],
        life_policies=[
            LifePolicyInput(
                id=1, person_id=1, name="Term cover", sum_assured=200_000,
                premium_annual=0.0, start_year=2026, end_year=2035,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )
    rows = simulate(plan)
    death_row = rows[4]  # 2030
    assert death_row.year == 2030
    assert death_row.life_cover_payout == 200_000
    # Payout is tax-free: no CAT charged on the life-cover proceeds themselves.
    assert death_row.cat_paid == 0.0
    # Cash jumps by the sum assured and stays (survivor keeps it).
    assert rows[3].asset_balances[1] == 10_000
    assert abs(rows[4].asset_balances[1] - 210_000) < 0.5
    assert abs(rows[5].asset_balances[1] - 210_000) < 0.5


def test_policy_expired_before_death_pays_nothing():
    plan = PlanInput(
        base_year=2026, projection_years=8,
        people=[_person(death_year=2033)],
        incomes=[],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=10_000, growth_rate=0.0, cost_basis=0.0)],
        life_policies=[
            LifePolicyInput(
                id=1, person_id=1, name="Lapsed cover", sum_assured=200_000,
                premium_annual=0.0, start_year=2026, end_year=2030,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )
    rows = simulate(plan)
    assert all(r.life_cover_payout == 0.0 for r in rows)


def test_cover_gap_closes_when_policy_clears_debt():
    """A death leaving a mortgage shows a cover gap; a term policy ≥ the debt
    closes it (payout → cash → liquid assets cover the outstanding debt)."""
    def _plan(sum_assured: float) -> PlanInput:
        policies = (
            [LifePolicyInput(id=1, person_id=1, name="Cover", sum_assured=sum_assured,
                             premium_annual=0.0, start_year=2026, end_year=2040)]
            if sum_assured > 0 else []
        )
        return PlanInput(
            base_year=2026, projection_years=5,
            people=[_person(death_year=2027), _person(pid=2, name="Conor")],
            incomes=[],
            expenses=[],
            assets=[AssetInput(id=1, name="Cash", kind="cash", value=20_000, growth_rate=0.0, cost_basis=0.0)],
            liabilities=[
                LiabilityInput(
                    id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                    interest_rate=0.0, term_months=300, start_year=2026,
                    monthly_payment=200_000.0 / 300,
                )
            ],
            life_policies=policies,
            assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
        )

    no_cover = simulate(_plan(0.0))[1]       # 2027, death year
    covered = simulate(_plan(250_000))[1]
    assert no_cover.cover_gap > 0            # debt outstrips liquid assets
    assert covered.cover_gap == 0.0          # payout clears it
