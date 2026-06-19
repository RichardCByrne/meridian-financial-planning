"""Scenario overrides for benefits-in-kind.

The scenario engine exposes a `benefits` bucket so a what-if can add an
employer perk (e.g. medical insurance) or override an existing benefit's value
without touching the base plan. These tests lock in that the override flows
through `apply_overrides` -> `simulate` and that malformed payloads are dropped
(consistent with the other `_added` buckets) and the input plan is never mutated.
"""

from datetime import date

from app.engine.scenario import apply_overrides
from app.engine.simulator import (
    AssumptionsInput,
    BenefitInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _base_plan(benefits: list[BenefitInput] | None = None) -> PlanInput:
    person = PersonInput(
        id=1, name="Worker", dob=date(1985, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    income = IncomeInput(
        id=1, person_id=1, kind="employment", name="Job",
        gross_amount=60_000, start_year=2026, end_year=None,
        escalation_rate=0.0, pays_prsi=True, pays_usc=True,
    )
    return PlanInput(
        base_year=2026, projection_years=1,
        people=[person], incomes=[income], expenses=[], assets=[],
        benefits=list(benefits or []),
        assumptions=AssumptionsInput(inflation_rate=0.0, state_pension_escalation_rate=0.0),
    )


def test_scenario_adds_a_benefit_raises_bik_and_tax():
    plan = _base_plan()
    base = simulate(plan)[0]
    overrides = {
        "benefits": {
            "_added": [
                {
                    "person_id": 1, "kind": "other", "name": "Gym + perks",
                    "start_year": 2026, "end_year": None, "amount": 5_000,
                }
            ]
        }
    }
    withb = simulate(apply_overrides(plan, overrides))[0]
    assert abs(withb.benefits_in_kind_total - 5_000) < 1
    assert withb.total_tax > base.total_tax
    # Cash gross is unchanged — BIK is notional pay, not cash.
    assert abs(withb.gross_income_total - base.gross_income_total) < 1


def test_scenario_overrides_existing_benefit_amount():
    benefit = BenefitInput(
        id=7, person_id=1, kind="other", name="Perk",
        start_year=2026, end_year=None, amount=2_000,
    )
    plan = _base_plan([benefit])
    base = simulate(plan)[0]
    assert abs(base.benefits_in_kind_total - 2_000) < 1

    bumped = simulate(apply_overrides(plan, {"benefits": {"7": {"amount": 8_000}}}))[0]
    assert abs(bumped.benefits_in_kind_total - 8_000) < 1
    assert bumped.total_tax > base.total_tax


def test_scenario_added_medical_insurance_gets_relief():
    plan = _base_plan()
    med = simulate(
        apply_overrides(
            plan,
            {
                "benefits": {
                    "_added": [
                        {
                            "person_id": 1, "kind": "medical_insurance", "name": "VHI",
                            "start_year": 2026, "end_year": None, "amount": 2_000,
                            "relief_adults": 1,
                        }
                    ]
                }
            },
        )
    )[0]
    other = simulate(
        apply_overrides(
            plan,
            {
                "benefits": {
                    "_added": [
                        {
                            "person_id": 1, "kind": "other", "name": "Perk",
                            "start_year": 2026, "end_year": None, "amount": 2_000,
                        }
                    ]
                }
            },
        )
    )[0]
    # Same taxable value, but medical insurance earns €200 relief (20% of the
    # €1,000 cap), so its income tax is exactly €200 lower.
    assert abs((other.income_tax - med.income_tax) - 200.0) < 1


def test_scenario_malformed_added_benefit_is_dropped():
    plan = _base_plan()
    overrides = {
        "benefits": {
            "_added": [
                {"name": "missing person + start_year", "amount": 1_000},  # invalid
                {
                    "person_id": 1, "kind": "other", "name": "Valid",
                    "start_year": 2026, "end_year": None, "amount": 3_000,
                },
            ]
        }
    }
    row = simulate(apply_overrides(plan, overrides))[0]
    # Only the valid benefit survives.
    assert abs(row.benefits_in_kind_total - 3_000) < 1


def test_apply_overrides_benefits_does_not_mutate_input():
    benefit = BenefitInput(
        id=7, person_id=1, kind="other", name="Perk",
        start_year=2026, end_year=None, amount=2_000,
    )
    plan = _base_plan([benefit])
    apply_overrides(
        plan,
        {
            "benefits": {
                "7": {"amount": 9_999},
                "_added": [
                    {
                        "person_id": 1, "kind": "other", "name": "Extra",
                        "start_year": 2026, "end_year": None, "amount": 1_000,
                    }
                ],
            }
        },
    )
    assert len(plan.benefits) == 1
    assert plan.benefits[0].amount == 2_000
