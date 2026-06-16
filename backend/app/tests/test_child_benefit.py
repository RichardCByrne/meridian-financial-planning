"""Child Benefit: tax-free monthly payment per child under the age limit,
escalation, and multi-child stacking."""

from datetime import date

from app.engine.simulator import (
    AssumptionsInput,
    ChildInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _basic_parent_plan(children: list[ChildInput], years: int = 5) -> PlanInput:
    parent = PersonInput(
        id=1, name="Parent", dob=date(1990, 1, 1),
        is_primary=True, life_expectancy=90, retirement_age=66,
    )
    return PlanInput(
        base_year=2026, projection_years=years,
        people=[parent], incomes=[], expenses=[], assets=[],
        children=children,
        assumptions=AssumptionsInput(inflation_rate=0.0, state_pension_escalation_rate=0.0),
    )


def test_child_benefit_pays_for_child_under_18():
    """One 5-year-old → €140 × 12 = €1,680 in year 0 (no escalation yet)."""
    child = ChildInput(id=1, name="Niamh", dob=date(2021, 1, 1))  # 5 in 2026
    plan = _basic_parent_plan([child], years=1)
    rows = simulate(plan)
    assert abs(rows[0].income_by_kind.get("child_benefit", 0) - 1_680) < 1


def test_child_benefit_stops_at_age_18():
    """Child turns 18 mid-projection → benefit drops to 0 from that year on."""
    # Born 2010 → 16 in 2026, 17 in 2027, 18 in 2028 (no benefit), 19 in 2029.
    child = ChildInput(id=1, name="Aoife", dob=date(2010, 1, 1))
    plan = _basic_parent_plan([child], years=4)
    rows = simulate(plan)
    assert abs(rows[0].income_by_kind.get("child_benefit", 0) - 1_680) < 1  # age 16
    assert abs(rows[1].income_by_kind.get("child_benefit", 0) - 1_680 * 1.0075) < 1  # age 17
    assert rows[2].income_by_kind.get("child_benefit", 0) == 0  # age 18
    assert rows[3].income_by_kind.get("child_benefit", 0) == 0  # age 19


def test_child_benefit_is_tax_free():
    """Benefit must not appear in any tax base. Parent with zero earned income
    pays zero IT/USC/PRSI despite the benefit being injected."""
    child = ChildInput(id=1, name="Cara", dob=date(2022, 1, 1))
    plan = _basic_parent_plan([child], years=1)
    rows = simulate(plan)
    assert rows[0].income_tax == 0
    assert rows[0].usc == 0
    assert rows[0].prsi == 0
    assert abs(rows[0].net_income_total - 1_680) < 1


def test_child_benefit_escalates_at_configured_rate():
    """Year 4 amount = €1,680 × (1.0075 ** 4) ≈ €1,730.91."""
    child = ChildInput(id=1, name="Roisin", dob=date(2020, 1, 1))
    plan = _basic_parent_plan([child], years=5)
    rows = simulate(plan)
    expected_year_4 = 1_680 * (1.0075 ** 4)
    assert abs(rows[4].income_by_kind.get("child_benefit", 0) - expected_year_4) < 1


def test_no_children_no_benefit():
    """Empty children list → no child_benefit line item."""
    plan = _basic_parent_plan([], years=1)
    rows = simulate(plan)
    assert "child_benefit" not in rows[0].income_by_kind


def test_multiple_children_stack():
    """Three children under 18 → benefit triples."""
    plan = _basic_parent_plan(
        [
            ChildInput(id=1, name="A", dob=date(2020, 1, 1)),
            ChildInput(id=2, name="B", dob=date(2022, 1, 1)),
            ChildInput(id=3, name="C", dob=date(2024, 1, 1)),
        ],
        years=1,
    )
    rows = simulate(plan)
    assert abs(rows[0].income_by_kind.get("child_benefit", 0) - 3 * 1_680) < 1
