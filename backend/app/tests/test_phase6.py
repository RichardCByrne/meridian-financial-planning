"""Phase 6 tests: scenario overrides + compare endpoint shape."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.engine.scenario import apply_overrides
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
from app.main import app


def _base_plan() -> PlanInput:
    return PlanInput(
        base_year=2026,
        projection_years=10,
        people=[
            PersonInput(
                id=1, name="Liam", dob=date(1990, 1, 1),
                is_primary=True, life_expectancy=90, retirement_age=66,
            )
        ],
        incomes=[
            IncomeInput(
                id=1, person_id=1, kind="employment", name="Salary",
                gross_amount=80_000, start_year=2026, end_year=None,
                escalation_rate=0.0, pays_prsi=True, pays_usc=True,
                pension_contribution_pct=0.0,
            )
        ],
        expenses=[
            ExpenseInput(
                id=1, name="Living", category="basic", amount=30_000,
                start_year=2026, end_year=None, escalation_rate=0.0,
            )
        ],
        assets=[
            AssetInput(
                id=1, name="Cash", kind="cash", value=20_000,
                growth_rate=0.0, cost_basis=0.0, owner_person_id=None,
            )
        ],
        liabilities=[],
        goals=[
            GoalInput(
                id=1, kind="milestone", name="Car",
                target_amount=20_000, target_year=2030,
            )
        ],
        assumptions=AssumptionsInput(
            inflation_rate=0.025, default_growth_rate=0.05,
            property_growth_rate=0.03, earnings_growth=0.0,
            state_pension_age=66,
        ),
    )


def test_apply_overrides_does_not_mutate_input():
    plan = _base_plan()
    overrides = {"incomes": {"1": {"gross_amount": 95_000}}}
    new_plan = apply_overrides(plan, overrides)
    assert plan.incomes[0].gross_amount == 80_000
    assert new_plan.incomes[0].gross_amount == 95_000
    assert new_plan is not plan


def test_apply_overrides_unknown_keys_silently_ignored():
    plan = _base_plan()
    overrides = {
        "incomes": {"999": {"gross_amount": 1.0}},  # id doesn't exist
        "people": {"1": {"not_a_field": "x", "retirement_age": 60}},  # mixed
        "garbage_bucket": {"1": {"foo": "bar"}},
    }
    new_plan = apply_overrides(plan, overrides)
    assert new_plan.incomes[0].gross_amount == 80_000
    assert new_plan.people[0].retirement_age == 60


def test_scenario_higher_salary_yields_higher_net_worth():
    plan = _base_plan()
    base_rows = simulate(plan)
    boosted = apply_overrides(plan, {"incomes": {"1": {"gross_amount": 120_000}}})
    boosted_rows = simulate(boosted)
    assert boosted_rows[-1].net_worth > base_rows[-1].net_worth


def test_added_income_models_promotion_mid_career():
    """Promotion: salary jumps by 40k starting 2030 — modelled as an _added income."""
    plan = _base_plan()
    base_rows = simulate(plan)
    promoted = apply_overrides(
        plan,
        {
            "incomes": {
                "_added": [
                    {
                        "person_id": 1,
                        "kind": "employment",
                        "name": "Promotion",
                        "gross_amount": 40_000,
                        "start_year": 2030,
                    }
                ]
            }
        },
    )
    promoted_rows = simulate(promoted)
    # Pre-2030: identical gross income.
    assert promoted_rows[0].gross_income_total == base_rows[0].gross_income_total
    assert promoted_rows[3].gross_income_total == base_rows[3].gross_income_total
    # 2030 onwards: +40k gross.
    assert promoted_rows[4].gross_income_total == pytest.approx(
        base_rows[4].gross_income_total + 40_000
    )
    # Final-year net worth higher.
    assert promoted_rows[-1].net_worth > base_rows[-1].net_worth


def test_added_expense_models_one_off_event():
    """One-off €25k wedding in 2028 modelled as an _added single_year expense."""
    plan = _base_plan()
    base_rows = simulate(plan)
    with_wedding = apply_overrides(
        plan,
        {
            "expenses": {
                "_added": [
                    {
                        "name": "Wedding",
                        "category": "single_year",
                        "amount": 25_000,
                        "start_year": 2028,
                    }
                ]
            }
        },
    )
    rows = simulate(with_wedding)
    # 2028 expenses jump by 25k.
    assert rows[2].expenses_total == pytest.approx(base_rows[2].expenses_total + 25_000)
    # 2027 expenses unchanged.
    assert rows[1].expenses_total == base_rows[1].expenses_total
    # 2029 expenses unchanged (single_year doesn't recur).
    assert rows[3].expenses_total == base_rows[3].expenses_total


def test_added_income_missing_required_field_silently_dropped():
    plan = _base_plan()
    out = apply_overrides(
        plan,
        {
            "incomes": {
                "_added": [
                    # missing gross_amount
                    {"person_id": 1, "kind": "employment", "name": "Bad", "start_year": 2030},
                    # well-formed
                    {"person_id": 1, "kind": "employment", "name": "Good",
                     "gross_amount": 20_000, "start_year": 2030},
                ]
            }
        },
    )
    # Only the well-formed entry was appended (1 base + 1 good = 2 incomes).
    assert len(out.incomes) == 2
    assert any(i.name == "Good" for i in out.incomes)


def test_net_worth_goal_status_uses_met_below_target():
    plan = _base_plan()
    # The base goal is a milestone — replace with net_worth for this test.
    plan_nw = apply_overrides(plan, {"goals": {"1": {"kind": "net_worth", "target_amount": 1_000_000_000}}})
    rows = simulate(plan_nw)
    target_row = next(r for r in rows if r.year == 2030)
    assert target_row.goal_status[1] == "below_target"


def test_scenario_assumptions_override_replaces_field():
    plan = _base_plan()
    overridden = apply_overrides(plan, {"assumptions": {"inflation_rate": 0.06, "state_pension_age": 67}})
    assert plan.assumptions.inflation_rate == 0.025
    assert overridden.assumptions.inflation_rate == 0.06
    assert overridden.assumptions.state_pension_age == 67
    # Other assumption fields unchanged.
    assert overridden.assumptions.default_growth_rate == plan.assumptions.default_growth_rate


def test_scenario_goal_target_year_override_moves_expense():
    plan = _base_plan()
    base_rows = simulate(plan)
    moved = apply_overrides(plan, {"goals": {"1": {"target_year": 2032}}})
    moved_rows = simulate(moved)
    # The €20k milestone moves from 2030 → 2032 (still inside the 10-year horizon).
    base_2030 = next(r for r in base_rows if r.year == 2030)
    moved_2030 = next(r for r in moved_rows if r.year == 2030)
    base_2032 = next(r for r in base_rows if r.year == 2032)
    moved_2032 = next(r for r in moved_rows if r.year == 2032)
    assert (
        base_2030.expenses_by_category.get("goals", 0)
        > moved_2030.expenses_by_category.get("goals", 0)
    )
    assert (
        moved_2032.expenses_by_category.get("goals", 0)
        > base_2032.expenses_by_category.get("goals", 0)
    )


def _make_plan_via_api(client: TestClient) -> int:
    p = client.post("/api/plans", json={"name": "Phase6", "base_year": 2026, "projection_years": 5}).json()
    plan_id = p["id"]
    person = client.post(
        f"/api/plans/{plan_id}/people",
        json={"name": "Liam", "dob": "1990-01-01", "is_primary": True, "retirement_age": 66},
    ).json()
    client.post(
        f"/api/people/{person['id']}/income",
        json={
            "kind": "employment", "name": "Salary",
            "gross_amount": 80_000, "start_year": 2026,
        },
    )
    client.post(
        f"/api/plans/{plan_id}/expenses",
        json={"name": "Living", "category": "basic", "amount": 30_000, "start_year": 2026},
    )
    client.post(
        f"/api/plans/{plan_id}/assets",
        json={"name": "Cash", "kind": "cash", "value": 20_000, "growth_rate": 0.0},
    )
    return plan_id


def test_scenario_crud_roundtrip():
    with TestClient(app) as client:
        plan_id = _make_plan_via_api(client)
        # Empty list
        listed = client.get(f"/api/plans/{plan_id}/scenarios").json()
        assert listed == []
        # Create
        s = client.post(
            f"/api/plans/{plan_id}/scenarios",
            json={"name": "Boosted salary", "overrides": {"assumptions": {"inflation_rate": 0.04}}},
        )
        assert s.status_code == 201
        sid = s.json()["id"]
        assert s.json()["overrides"] == {"assumptions": {"inflation_rate": 0.04}}
        # Patch
        patched = client.patch(
            f"/api/scenarios/{sid}",
            json={"overrides": {"assumptions": {"inflation_rate": 0.05}}},
        ).json()
        assert patched["overrides"]["assumptions"]["inflation_rate"] == 0.05
        # Delete
        del_resp = client.delete(f"/api/scenarios/{sid}")
        assert del_resp.status_code == 204
        assert client.get(f"/api/plans/{plan_id}/scenarios").json() == []


def test_projection_with_scenario_id_differs_from_base():
    with TestClient(app) as client:
        plan_id = _make_plan_via_api(client)
        s = client.post(
            f"/api/plans/{plan_id}/scenarios",
            json={"name": "Lower expenses", "overrides": {"expenses": {}}},
        ).json()
        # Find the expense id by listing the plan's expenses.
        expenses = client.get(f"/api/plans/{plan_id}/expenses").json()
        eid = expenses[0]["id"]
        client.patch(
            f"/api/scenarios/{s['id']}",
            json={"overrides": {"expenses": {str(eid): {"amount": 10_000}}}},
        )
        base = client.get(f"/api/plans/{plan_id}/projection").json()
        scen = client.get(f"/api/plans/{plan_id}/projection?scenario_id={s['id']}").json()
        assert scen["summary"]["final_net_worth"] > base["summary"]["final_net_worth"]


def test_compare_endpoint_shape_and_delta():
    with TestClient(app) as client:
        plan_id = _make_plan_via_api(client)
        # Find income id
        people = client.get(f"/api/plans/{plan_id}/people").json()
        person_id = people[0]["id"]
        incomes = client.get(f"/api/people/{person_id}/income").json()
        iid = incomes[0]["id"]
        s = client.post(
            f"/api/plans/{plan_id}/scenarios",
            json={
                "name": "Higher salary",
                "overrides": {"incomes": {str(iid): {"gross_amount": 120_000}}},
            },
        ).json()
        resp = client.get(f"/api/plans/{plan_id}/compare?b={s['id']}").json()
        assert resp["a"]["scenario_name"] == "Base"
        assert resp["b"]["scenario_name"] == "Higher salary"
        assert len(resp["delta"]) == 5  # projection_years
        # Higher salary → positive net-worth delta accumulates over time.
        assert resp["delta"][-1]["net_worth_delta"] > 0
        # Delta with same series on both sides is zero.
        same = client.get(f"/api/plans/{plan_id}/compare?a={s['id']}&b={s['id']}").json()
        assert all(d["net_worth_delta"] == 0 for d in same["delta"])
