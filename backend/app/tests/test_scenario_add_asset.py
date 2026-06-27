"""Scenario lever: add a brand-new asset (and the liability financing it) to
model a hypothetical purchase — e.g. buying a buy-to-let property with its own
BTL mortgage — and see the effect on the projection.

The added asset gets an id well below the simulator's reserved synthetic asset
ids (cash = -1, PRSA = -1000-pid, ARF = -2000-pid) so it never aliases an
auto-created wrapper. An added asset links to an added mortgage via `_ref` /
`_linked_liability_ref`.
"""

from datetime import date

from app.engine.scenario import apply_overrides
from app.engine.simulator import (
    AssumptionsInput,
    IncomeInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _plan() -> PlanInput:
    return PlanInput(
        base_year=2026, projection_years=6,
        people=[
            PersonInput(
                id=1, name="Liam", dob=date(1985, 1, 1),
                is_primary=True, life_expectancy=95, retirement_age=66,
            )
        ],
        incomes=[
            IncomeInput(
                id=1, person_id=1, kind="employment", name="Salary",
                gross_amount=120_000, start_year=2026, end_year=None,
                escalation_rate=0.0, pays_prsi=True, pays_usc=True,
            )
        ],
        expenses=[], assets=[],
        assumptions=AssumptionsInput(inflation_rate=0.0, state_pension_escalation_rate=0.0),
    )


_BTL = {
    "assets": {
        "_added": [{
            "name": "BTL flat", "kind": "property_btl", "value": 300_000,
            "purchase_year": 2027, "deposit": 60_000, "growth_rate": 0.0,
            "owner_person_id": 1, "_linked_liability_ref": "m",
        }]
    },
    "liabilities": {
        "_added": [{
            "_ref": "m", "name": "BTL mortgage", "kind": "mortgage",
            "principal": 240_000, "interest_rate": 0.05, "term_months": 300,
            "start_year": 2027,
        }]
    },
}


def _rows(plan):
    return {r.year: r for r in simulate(plan)}


def test_added_btl_property_and_mortgage_appear_after_purchase():
    scenario = apply_overrides(_plan(), _BTL)
    rows = _rows(scenario)
    # 2026: not bought yet — no BTL asset, no mortgage.
    assert rows[2026].asset_balances_by_kind.get("property_btl", 0.0) == 0.0
    assert rows[2026].debt_outstanding == 0.0
    # 2027: property on the books at face value, mortgage live.
    assert abs(rows[2027].asset_balances_by_kind["property_btl"] - 300_000) < 1
    assert rows[2027].debt_outstanding > 0


def test_added_asset_id_does_not_alias_cash_bucket():
    scenario = apply_overrides(_plan(), _BTL)
    rows = _rows(scenario)
    # High income with no expenses → surplus accumulates as real cash, and the
    # BTL property coexists. If the added asset aliased the cash synthetic id,
    # one would clobber the other.
    assert rows[2027].asset_balances_by_kind["property_btl"] > 0
    assert rows[2027].asset_balances_by_kind.get("cash", 0.0) > 0
    # Added asset id sits below the reserved range.
    btl_ids = [aid for aid in rows[2027].asset_balances if aid <= -1_000_000]
    assert len(btl_ids) == 1


def test_mortgage_payment_auto_computed_and_amortises():
    scenario = apply_overrides(_plan(), _BTL)
    rows = _rows(scenario)
    # No monthly_payment supplied → derived from principal/rate/term, so the
    # balance falls year on year.
    bal_2027 = sum(rows[2027].liability_balances.values())
    bal_2028 = sum(rows[2028].liability_balances.values())
    assert 0 < bal_2028 < bal_2027 <= 240_000


def test_deposit_paid_from_cash_on_purchase():
    base = _rows(apply_overrides(_plan(), None))
    scen = _rows(apply_overrides(_plan(), _BTL))
    # In 2027 the scenario's cash is lower than the no-purchase baseline by the
    # €60k deposit plus that year's mortgage debt service (same income, no other
    # differences).
    base_cash = base[2027].asset_balances_by_kind.get("cash", 0.0)
    scen_cash = scen[2027].asset_balances_by_kind.get("cash", 0.0)
    debt_service = scen[2027].expenses_by_category.get("debt_service", 0.0)
    assert debt_service > 0
    assert abs((base_cash - scen_cash) - (60_000 + debt_service)) < 1


def test_disposal_clears_linked_mortgage():
    overrides = {
        "assets": {"_added": [{**_BTL["assets"]["_added"][0], "disposal_year": 2030}]},
        "liabilities": _BTL["liabilities"],
    }
    rows = _rows(apply_overrides(_plan(), overrides))
    assert rows[2029].debt_outstanding > 0      # mortgage still live
    assert rows[2030].debt_outstanding == 0.0   # disposal settled it
    assert rows[2030].asset_balances_by_kind.get("property_btl", 0.0) == 0.0


def test_linked_liability_id_to_base_plan_liability():
    # An added asset may link to an existing base-plan liability by numeric id.
    plan = _plan()
    overrides = {
        "assets": {"_added": [{
            "name": "X", "kind": "property_btl", "value": 100_000,
            "purchase_year": 2027, "owner_person_id": 1, "linked_liability_id": 5,
        }]},
    }
    scenario = apply_overrides(plan, overrides)
    added = [a for a in scenario.assets if a.id <= -1_000_000]
    assert len(added) == 1
    assert added[0].linked_liability_id == 5


def test_malformed_added_asset_or_liability_dropped():
    overrides = {
        "assets": {"_added": [{"name": "no value"}, "not-a-dict"]},
        "liabilities": {"_added": [{"name": "no principal"}]},
    }
    scenario = apply_overrides(_plan(), overrides)
    assert scenario.assets == []
    assert scenario.liabilities == []


def test_apply_overrides_does_not_mutate_input():
    plan = _plan()
    apply_overrides(plan, _BTL)
    assert plan.assets == []
    assert plan.liabilities == []
