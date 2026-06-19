"""Planned asset transactions (Phase 1): future purchase (deposit out of cash,
dormant until purchase_year) and deliberate disposal (proceeds into cash).
Composes to model buying a second home and moving house."""

from datetime import date

from fastapi.testclient import TestClient

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    PersonInput,
    PlanInput,
    simulate,
)
from app.main import app


def _person() -> PersonInput:
    return PersonInput(id=1, name="Cara", dob=date(1985, 1, 1), is_primary=True, life_expectancy=95)


def _plan(assets: list[AssetInput], years: int = 12) -> PlanInput:
    return PlanInput(
        base_year=2026, projection_years=years,
        people=[_person()], incomes=[], expenses=[],
        assets=assets,
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )


def test_future_purchase_is_dormant_until_its_year():
    """A house bought in 2030 holds no value before then; on purchase it appears
    at face value and the deposit leaves cash."""
    plan = _plan([
        AssetInput(id=1, name="Cash", kind="cash", value=200_000, growth_rate=0.0, cost_basis=0.0),
        AssetInput(
            id=2, name="Holiday home", kind="property_primary", value=300_000,
            growth_rate=0.0, cost_basis=0.0, purchase_year=2030, deposit=80_000,
        ),
    ])
    rows = simulate(plan)
    # 2026–2029: dormant, no value, full cash, net worth = cash only.
    for i in range(4):
        assert rows[i].asset_balances.get(2, 0.0) == 0.0
        assert rows[i].asset_balances[1] == 200_000
        assert rows[i].net_worth == 200_000
    # 2030 (index 4): house appears at 300k, cash down by the 80k deposit.
    assert rows[4].asset_balances[2] == 300_000
    assert rows[4].asset_balances[1] == 120_000
    # No mortgage in this plan, so the 220k financed portion shows as new equity
    # (net worth rises by value − deposit). A coupled mortgage liability offsets
    # it — see the move-house sanity in the engine docstring / Phase 2.
    assert rows[4].net_worth == 420_000


def test_planned_disposal_moves_proceeds_to_cash_tax_free_for_home():
    """Primary residence sold in 2030: balance → cash, PPR-exempt (no tax)."""
    plan = _plan([
        AssetInput(id=1, name="Cash", kind="cash", value=10_000, growth_rate=0.0, cost_basis=0.0),
        AssetInput(
            id=2, name="Home", kind="property_primary", value=400_000,
            growth_rate=0.0, cost_basis=250_000, disposal_year=2030,
        ),
    ])
    rows = simulate(plan)
    # Before sale: home present.
    assert rows[3].asset_balances[2] == 400_000
    # 2030: sold, proceeds (gain included) land in cash tax-free.
    assert rows[4].asset_balances.get(2, 0.0) == 0.0
    assert rows[4].asset_balances[1] == 410_000
    assert rows[4].net_worth == 410_000


def test_planned_disposal_of_etf_applies_exit_tax():
    """ETF sold deliberately pays 41% exit tax on the gain; net lands in cash."""
    plan = _plan([
        AssetInput(id=1, name="Cash", kind="cash", value=0.0, growth_rate=0.0, cost_basis=0.0),
        AssetInput(
            id=2, name="Fund", kind="etf_fund", value=100_000,
            growth_rate=0.0, cost_basis=60_000, disposal_year=2028,
        ),
    ])
    rows = simulate(plan)
    # Gain = 40k, exit tax 41% = 16.4k → net proceeds 83.6k into cash.
    assert abs(rows[2].asset_balances[1] - 83_600) < 1.0
    assert rows[2].asset_balances.get(2, 0.0) == 0.0


def test_move_house_sell_old_buy_new_same_year():
    """Move house: sell the old home and buy a dearer one in the same year; equity
    flows through cash."""
    plan = _plan([
        AssetInput(id=1, name="Cash", kind="cash", value=50_000, growth_rate=0.0, cost_basis=0.0),
        AssetInput(
            id=2, name="Old home", kind="property_primary", value=350_000,
            growth_rate=0.0, cost_basis=200_000, disposal_year=2031,
        ),
        AssetInput(
            id=3, name="New home", kind="property_primary", value=500_000,
            growth_rate=0.0, cost_basis=0.0, purchase_year=2031, deposit=350_000,
        ),
    ])
    rows = simulate(plan)
    # 2030: old home present, new dormant.
    assert rows[4].asset_balances[2] == 350_000
    assert rows[4].asset_balances.get(3, 0.0) == 0.0
    # 2031: old sold (+350k cash), new bought (-350k deposit), so cash unchanged
    # at 50k; new home worth 500k.
    assert rows[5].asset_balances.get(2, 0.0) == 0.0
    assert rows[5].asset_balances[3] == 500_000
    assert rows[5].asset_balances[1] == 50_000


def test_property_transaction_fields_round_trip_through_api():
    with TestClient(app) as client:
        pid = client.post(
            "/api/plans",
            json={"name": "Move household", "base_year": 2026, "projection_years": 15},
        ).json()["id"]
        created = client.post(
            f"/api/plans/{pid}/assets",
            json={
                "name": "Second home", "kind": "property_btl", "value": 320_000,
                "growth_rate": 0.03, "purchase_year": 2030, "deposit": 64_000,
                "disposal_year": 2045,
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["purchase_year"] == 2030
        assert body["deposit"] == 64_000
        assert body["disposal_year"] == 2045
        # Projection runs without error and the asset is dormant in year 1.
        proj = client.get(f"/api/plans/{pid}/projection")
        assert proj.status_code == 200
        first = proj.json()["years"][0]
        assert first["asset_balances"].get(str(body["id"]), 0.0) == 0.0