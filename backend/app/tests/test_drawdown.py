"""ARF band-fill decumulation: draw the ARF up to the top of the standard-rate
band using cheap 20% headroom left by other income."""

from datetime import date

from app.config.tax_ie_2026 import IRELAND_2026_OFFICIAL as CFG
from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    PersonInput,
    PlanInput,
    simulate,
)


def _retiree(band_fill: bool) -> PersonInput:
    # Born 1958 → age 68 in base year 2026, already retired (retirement_age 66).
    return PersonInput(
        id=1, name="Retiree", dob=date(1958, 1, 1), is_primary=True,
        life_expectancy=95, retirement_age=66, arf_band_fill=band_fill,
    )


def _plan(band_fill: bool, years: int = 3) -> PlanInput:
    return PlanInput(
        base_year=2026, projection_years=years,
        people=[_retiree(band_fill)], incomes=[], expenses=[],
        assets=[
            AssetInput(id=1, name="ARF", kind="arf", value=500_000,
                       growth_rate=0.0, cost_basis=0.0, owner_person_id=1),
            AssetInput(id=2, name="Cash", kind="cash", value=0.0, growth_rate=0.0, cost_basis=0.0),
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0, default_growth_rate=0.0),
    )


def test_band_fill_draws_arf_up_to_standard_rate_band():
    default = simulate(_plan(band_fill=False))[0]
    filled = simulate(_plan(band_fill=True))[0]

    state_pension = default.state_pension_total
    srco = CFG.srco_single
    # Band-fill tops the ARF drawdown up to the standard-rate ceiling given the
    # state pension already received.
    expected_fill = srco - state_pension
    assert filled.income_by_kind["arf_drawdown"] > default.income_by_kind["arf_drawdown"]
    assert abs(filled.income_by_kind["arf_drawdown"] - expected_fill) < 1.0
    # Total taxable income lands right at the band, so nothing is taxed at the
    # higher rate this year.
    assert abs((state_pension + filled.income_by_kind["arf_drawdown"]) - srco) < 1.0


def test_band_fill_respects_statutory_minimum_floor():
    """When the band headroom is smaller than the statutory minimum, the ARF
    still draws at least the statutory minimum."""
    # A €2M pot: 4% statutory minimum = €80k, far above the ~€28k band headroom.
    plan = _plan(band_fill=True)
    plan.assets[0] = AssetInput(id=1, name="ARF", kind="arf", value=2_000_000,
                                growth_rate=0.0, cost_basis=0.0, owner_person_id=1)
    row = simulate(plan)[0]
    statutory = 2_000_000 * CFG.arf_min_drawdown_60_69  # 4%
    assert abs(row.income_by_kind["arf_drawdown"] - statutory) < 1.0


def test_band_fill_off_matches_statutory_minimum():
    row = simulate(_plan(band_fill=False))[0]
    statutory = 500_000 * CFG.arf_min_drawdown_60_69
    assert abs(row.income_by_kind["arf_drawdown"] - statutory) < 1.0
