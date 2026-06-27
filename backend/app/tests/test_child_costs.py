"""Per-child rearing costs: age-gated childcare / primary / secondary (with an
optional private-fee top-up) and an opt-in everyday (food/clothes) line. The
simulator applies each over the matching life stage based on the child's age,
escalates by inflation, and folds the total into the "children" expense
category. Inactive (scenario-disabled) children contribute nothing.

Stage boundaries (TaxConfig defaults): childcare 0–4, primary 5–12,
secondary 13–17, everyday 0–17.
"""

from datetime import date

from fastapi.testclient import TestClient

from app.engine.scenario import apply_overrides
from app.engine.simulator import (
    AssumptionsInput,
    ChildInput,
    PersonInput,
    PlanInput,
    simulate,
)
from app.main import app


def _plan(child: ChildInput, *, years: int = 20, inflation: float = 0.0) -> PlanInput:
    parent = PersonInput(
        id=1, name="Parent", dob=date(1990, 1, 1),
        is_primary=True, life_expectancy=120, retirement_age=66,
    )
    return PlanInput(
        base_year=2026, projection_years=years,
        people=[parent], incomes=[], expenses=[], assets=[],
        children=[child],
        assumptions=AssumptionsInput(
            inflation_rate=inflation, state_pension_escalation_rate=0.0
        ),
    )


def _children_cost(plan: PlanInput, year: int) -> float:
    rows = {r.year: r for r in simulate(plan)}
    return rows[year].expenses_by_category.get("children", 0.0)


def test_costs_apply_only_in_their_age_band():
    # dob 2024 → age 2 (2026), 5 (2029), 13 (2037), 18 (2042).
    child = ChildInput(
        id=1, name="A", dob=date(2024, 1, 1),
        childcare_annual=1_000.0,
        primary_annual=2_000.0,
        secondary_annual=3_000.0,
    )
    plan = _plan(child)
    assert abs(_children_cost(plan, 2026) - 1_000.0) < 1  # age 2 → childcare
    assert abs(_children_cost(plan, 2028) - 1_000.0) < 1  # age 4 → still childcare
    assert abs(_children_cost(plan, 2029) - 2_000.0) < 1  # age 5 → primary
    assert abs(_children_cost(plan, 2036) - 2_000.0) < 1  # age 12 → still primary
    assert abs(_children_cost(plan, 2037) - 3_000.0) < 1  # age 13 → secondary
    assert abs(_children_cost(plan, 2041) - 3_000.0) < 1  # age 17 → still secondary
    assert _children_cost(plan, 2042) == 0.0              # age 18 → aged out


def test_everyday_runs_full_span_and_stacks():
    child = ChildInput(
        id=1, name="A", dob=date(2024, 1, 1),
        childcare_annual=1_000.0,
        everyday_annual=500.0,
    )
    plan = _plan(child)
    assert abs(_children_cost(plan, 2026) - 1_500.0) < 1  # childcare + everyday
    assert abs(_children_cost(plan, 2037) - 500.0) < 1    # everyday only (no secondary set)
    assert _children_cost(plan, 2042) == 0.0              # everyday stops at 18


def test_everyday_default_off_avoids_double_count():
    child = ChildInput(id=1, name="A", dob=date(2024, 1, 1), childcare_annual=1_000.0)
    plan = _plan(child)
    # everyday_annual defaults to 0 → only the childcare cost shows.
    assert abs(_children_cost(plan, 2026) - 1_000.0) < 1


def test_private_fee_stacks_only_during_secondary_and_only_when_private():
    base = dict(id=1, name="A", dob=date(2024, 1, 1),
                secondary_annual=3_000.0, secondary_private_fee_annual=5_000.0)
    public = _plan(ChildInput(**base, secondary_is_private=False))
    private = _plan(ChildInput(**base, secondary_is_private=True))
    # age 13 (2037): public secondary only vs public + private fee.
    assert abs(_children_cost(public, 2037) - 3_000.0) < 1
    assert abs(_children_cost(private, 2037) - 8_000.0) < 1
    # Private fee never applies outside secondary (age 5, 2029).
    assert _children_cost(private, 2029) == 0.0


def test_costs_escalate_with_inflation():
    # dob 2026 → age 0 at base year, still childcare for years 0..4.
    child = ChildInput(id=1, name="A", dob=date(2026, 1, 1), childcare_annual=1_000.0)
    plan = _plan(child, inflation=0.10)
    assert abs(_children_cost(plan, 2026) - 1_000.0) < 1       # elapsed 0
    assert abs(_children_cost(plan, 2027) - 1_100.0) < 1       # ×1.10
    assert abs(_children_cost(plan, 2028) - 1_000.0 * 1.1**2) < 1


def test_costs_reduce_household_cash_flow():
    # Adding a €1,000 cost should lower the year's surplus by exactly €1,000
    # versus the same child with no costs (Child Benefit is unchanged either way).
    free = simulate(_plan(ChildInput(id=1, name="A", dob=date(2024, 1, 1))))[0]
    costed = simulate(
        _plan(ChildInput(id=1, name="A", dob=date(2024, 1, 1), childcare_annual=1_000.0))
    )[0]
    assert abs(costed.expenses_total - free.expenses_total - 1_000.0) < 1
    assert abs((free.surplus_or_shortfall - costed.surplus_or_shortfall) - 1_000.0) < 1


def test_inactive_child_has_no_costs():
    child = ChildInput(
        id=1, name="A", dob=date(2024, 1, 1), childcare_annual=1_000.0, active=False
    )
    plan = _plan(child)
    assert "children" not in simulate(plan)[0].expenses_by_category


def test_scenario_disabling_child_drops_costs():
    child = ChildInput(id=1, name="A", dob=date(2024, 1, 1), childcare_annual=1_000.0)
    plan = _plan(child)
    assert abs(_children_cost(plan, 2026) - 1_000.0) < 1

    scenario = apply_overrides(plan, {"children": {"1": {"active": False}}})
    assert "children" not in simulate(scenario)[0].expenses_by_category
    # Base plan untouched.
    assert abs(_children_cost(plan, 2026) - 1_000.0) < 1


def test_child_cost_fields_round_trip_through_api():
    with TestClient(app) as client:
        plan_id = client.post(
            "/api/plans", json={"name": "Costs", "base_year": 2026, "projection_years": 1}
        ).json()["id"]
        resp = client.post(
            f"/api/plans/{plan_id}/children",
            json={
                "name": "A",
                "dob": "2024-01-01",
                "childcare_annual": 12_000.0,
                "secondary_is_private": True,
                "secondary_private_fee_annual": 6_000.0,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["childcare_annual"] == 12_000.0
        assert body["secondary_is_private"] is True
        assert body["secondary_private_fee_annual"] == 6_000.0
        # Unset cost fields default to 0.
        assert body["primary_annual"] == 0.0
        assert body["everyday_annual"] == 0.0

        # Patch one field; others persist.
        child_id = body["id"]
        patched = client.patch(
            f"/api/children/{child_id}", json={"everyday_annual": 3_000.0}
        ).json()
        assert patched["everyday_annual"] == 3_000.0
        assert patched["childcare_annual"] == 12_000.0


def test_negative_child_cost_rejected_by_api():
    with TestClient(app) as client:
        plan_id = client.post(
            "/api/plans", json={"name": "Neg", "base_year": 2026, "projection_years": 1}
        ).json()["id"]
        resp = client.post(
            f"/api/plans/{plan_id}/children",
            json={"name": "A", "dob": "2024-01-01", "childcare_annual": -5.0},
        )
        assert resp.status_code == 422
