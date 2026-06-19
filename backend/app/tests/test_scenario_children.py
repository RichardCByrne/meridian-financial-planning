"""Scenario lever for family size: add a child or disable one to model a
different number of children, and watch Child Benefit move accordingly."""

from datetime import date

from app.engine.scenario import apply_overrides
from app.engine.simulator import (
    AssumptionsInput,
    ChildInput,
    PersonInput,
    PlanInput,
    simulate,
)

# €140/mo × 12, no escalation in the base year.
_ONE_CHILD_YEAR0 = 1_680.0


def _plan(children: list[ChildInput]) -> PlanInput:
    parent = PersonInput(
        id=1, name="Parent", dob=date(1990, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    return PlanInput(
        base_year=2026, projection_years=1,
        people=[parent], incomes=[], expenses=[], assets=[],
        children=children,
        assumptions=AssumptionsInput(inflation_rate=0.0, state_pension_escalation_rate=0.0),
    )


def _benefit(plan: PlanInput) -> float:
    return simulate(plan)[0].income_by_kind.get("child_benefit", 0.0)


def test_scenario_adds_a_child_raises_child_benefit():
    """Base has one child; a scenario adds a second → benefit doubles."""
    plan = _plan([ChildInput(id=1, name="A", dob=date(2022, 1, 1))])
    assert abs(_benefit(plan) - _ONE_CHILD_YEAR0) < 1

    scenario = apply_overrides(
        plan,
        {"children": {"_added": [{"name": "Second child", "dob": "2024-01-01"}]}},
    )
    assert abs(_benefit(scenario) - 2 * _ONE_CHILD_YEAR0) < 1
    # Base plan is untouched.
    assert abs(_benefit(plan) - _ONE_CHILD_YEAR0) < 1


def test_scenario_disables_a_child_drops_child_benefit():
    """Two base children; a scenario excludes one → benefit halves."""
    plan = _plan([
        ChildInput(id=1, name="A", dob=date(2022, 1, 1)),
        ChildInput(id=2, name="B", dob=date(2024, 1, 1)),
    ])
    assert abs(_benefit(plan) - 2 * _ONE_CHILD_YEAR0) < 1

    scenario = apply_overrides(plan, {"children": {"2": {"active": False}}})
    assert abs(_benefit(scenario) - _ONE_CHILD_YEAR0) < 1
    # Base plan still counts both children.
    assert abs(_benefit(plan) - 2 * _ONE_CHILD_YEAR0) < 1


def test_scenario_disable_all_children_zeroes_benefit():
    plan = _plan([ChildInput(id=1, name="A", dob=date(2022, 1, 1))])
    scenario = apply_overrides(plan, {"children": {"1": {"active": False}}})
    assert "child_benefit" not in simulate(scenario)[0].income_by_kind


def test_added_child_with_future_dob_pays_only_once_born():
    """A child added with a future birth year contributes nothing until born."""
    plan = _plan([])
    scenario = apply_overrides(
        plan,
        {"children": {"_added": [{"name": "Future", "dob": "2030-01-01"}]}},
    )
    # base_year 2026, child born 2030 → no benefit in the single simulated year.
    assert "child_benefit" not in simulate(scenario)[0].income_by_kind


def test_malformed_added_child_is_dropped():
    """A bad _added payload (missing dob) is silently ignored, never 500s."""
    plan = _plan([ChildInput(id=1, name="A", dob=date(2022, 1, 1))])
    scenario = apply_overrides(
        plan,
        {"children": {"_added": [{"name": "No DOB"}, {"name": "Bad date", "dob": "not-a-date"}]}},
    )
    # Only the original child remains.
    assert abs(_benefit(scenario) - _ONE_CHILD_YEAR0) < 1


def test_apply_overrides_children_does_not_mutate_input():
    plan = _plan([ChildInput(id=1, name="A", dob=date(2022, 1, 1))])
    apply_overrides(plan, {"children": {"1": {"active": False}}})
    assert len(plan.children) == 1
    assert plan.children[0].active is True
