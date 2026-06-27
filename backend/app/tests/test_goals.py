"""Goals: cost-bearing goals as expenses + goal-status resolution."""

from datetime import date

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    ExpenseInput,
    GoalInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _employee() -> PersonInput:
    return PersonInput(
        id=1, name="Liam", dob=date(1990, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
    )


def _salary(gross: float = 80_000) -> IncomeInput:
    return IncomeInput(
        id=1, person_id=1, kind="employment", name="Salary",
        gross_amount=gross, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
        pension_contribution_pct=0.0,
    )


def _cash(value: float = 50_000) -> AssetInput:
    return AssetInput(
        id=1, name="Cash", kind="cash", value=value,
        growth_rate=0.0, cost_basis=0.0, owner_person_id=None,
    )


def _spend_plan(kind: str) -> PlanInput:
    return PlanInput(
        base_year=2026, projection_years=4,
        people=[_employee()],
        incomes=[_salary()],
        expenses=[],
        assets=[_cash()],
        assumptions=AssumptionsInput(),
        goals=[GoalInput(id=10, kind=kind, name="New car", target_amount=30_000, target_year=2028)],
    )


def test_spend_goal_becomes_expense_in_target_year():
    rows = simulate(_spend_plan("spend"))
    # Year 2026 (idx 0): no goal expense.
    assert "goals" not in rows[0].expenses_by_category
    # Year 2028 (idx 2): 30k goal expense.
    assert abs(rows[2].expenses_by_category.get("goals", 0) - 30_000) < 1
    # Status: pending in 2026/27, achieved in 2028, achieved (sticky) in 2029.
    assert rows[0].goal_status[10] == "pending"
    assert rows[1].goal_status[10] == "pending"
    assert rows[2].goal_status[10] == "achieved"
    assert rows[3].goal_status[10] == "achieved"


def test_legacy_spend_kinds_still_behave_as_one_off_costs():
    # Un-migrated rows (or old scenario data) keep working as one-off spends.
    for legacy in ("milestone", "education", "gift", "pre_retirement_spend"):
        rows = simulate(_spend_plan(legacy))
        assert abs(rows[2].expenses_by_category.get("goals", 0) - 30_000) < 1
        assert rows[2].goal_status[10] == "achieved"


def test_goal_schema_normalises_legacy_kinds_to_spend():
    from app.schemas.goal import GoalCreate

    for legacy in ("milestone", "education", "gift", "pre_retirement_spend"):
        g = GoalCreate(kind=legacy, name="X", target_amount=1_000, target_year=2030)
        assert g.kind == "spend"
    # Canonical kinds pass through unchanged.
    for canonical in ("spend", "net_worth", "retirement"):
        assert GoalCreate(kind=canonical, name="X", target_amount=0, target_year=2030).kind == canonical


def test_net_worth_goal_evaluates_at_target_year():
    """Aspirational €1M net worth by 2030. With 50k cash + 80k salary, won't make it."""
    goal = GoalInput(
        id=20, kind="net_worth", name="Millionaire by 30", target_amount=1_000_000, target_year=2030,
    )
    plan = PlanInput(
        base_year=2026, projection_years=5,
        people=[_employee()], incomes=[_salary()],
        expenses=[ExpenseInput(id=1, name="Living", category="basic", amount=40_000, start_year=2026, end_year=None, escalation_rate=0.0)],
        assets=[_cash()],
        assumptions=AssumptionsInput(),
        goals=[goal],
    )
    rows = simulate(plan)
    # 2030 = idx 4. Net worth nowhere near 1M.
    assert rows[4].net_worth < 1_000_000
    assert rows[4].goal_status[20] == "below_target"


def test_net_worth_goal_achieved_when_target_met():
    goal = GoalInput(
        id=30, kind="net_worth", name="100k by 2027", target_amount=100_000, target_year=2027,
    )
    plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[_employee()], incomes=[_salary()], expenses=[],
        assets=[AssetInput(id=1, name="Big cash", kind="cash", value=200_000, growth_rate=0.0, cost_basis=0.0, owner_person_id=None)],
        assumptions=AssumptionsInput(),
        goals=[goal],
    )
    rows = simulate(plan)
    # 2027 = idx 1. Net worth >= 100k easily.
    assert rows[1].net_worth >= 100_000
    assert rows[1].goal_status[30] == "met"


def test_retirement_goal_is_informational():
    goal = GoalInput(
        id=40, kind="retirement", name="Retire", target_amount=0, target_year=2056,
        linked_person_id=1,
    )
    plan = PlanInput(
        base_year=2026, projection_years=31,
        people=[_employee()], incomes=[_salary()], expenses=[],
        assets=[_cash()],
        assumptions=AssumptionsInput(),
        goals=[goal],
    )
    rows = simulate(plan)
    # Pending until 2056, achieved at and after.
    assert rows[0].goal_status[40] == "pending"
    assert rows[30].goal_status[40] == "achieved"
    # No goal expense — retirement goal doesn't add cost.
    assert all("goals" not in r.expenses_by_category for r in rows)
