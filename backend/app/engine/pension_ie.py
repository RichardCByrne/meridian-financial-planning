"""Ireland pension lifecycle helpers.

Pure functions, no DB or HTTP deps. Reads tax-rule constants from a
`TaxConfig` (defaults to `IRELAND_2026_OFFICIAL` if none passed).

Scope:
- Age-related contribution cap (15%–40% of earnings, earnings capped at €115k).
- Pension lump-sum tax bands (€200k tax-free / next €300k @ 20% / above @ marginal).
- ARF imputed-distribution minimum drawdown percentages.
"""

from __future__ import annotations

from app.engine.tax_config import TaxConfig, resolve as _config
from app.engine.tax_ie import progressive_tax


def age_contribution_cap_pct(age: int, tax_config: TaxConfig | None = None) -> float:
    """Maximum tax-relievable pension contribution as % of net relevant earnings, by age."""
    cfg = _config(tax_config)
    for max_age, pct in cfg.pension_contribution_limits_by_age:
        if age <= max_age:
            return pct
    return cfg.pension_contribution_limits_by_age[-1][1]


def relievable_contribution(
    gross_earnings: float, requested_pct: float, age: int, tax_config: TaxConfig | None = None
) -> float:
    """Return the tax-deductible contribution amount given:
    - gross earnings (capped at €115k for relief purposes)
    - requested contribution % of earnings
    - employee age (drives the upper cap)
    """
    if gross_earnings <= 0 or requested_pct <= 0:
        return 0.0
    cfg = _config(tax_config)
    cap_pct = age_contribution_cap_pct(age, cfg)
    effective_pct = min(requested_pct, cap_pct)
    capped_earnings = min(gross_earnings, cfg.pension_earnings_cap)
    return capped_earnings * effective_pct


def lump_sum_tax(lump_sum: float, tax_config: TaxConfig | None = None) -> float:
    """Tax due on a pension retirement lump sum.

    First €200k tax-free, next €300k (up to €500k cumulative) at 20%, anything
    above the SFT lump-sum cap is taxed at the marginal rate (40% by default).
    """
    cfg = _config(tax_config)
    return progressive_tax(
        lump_sum,
        (
            (cfg.pension_tax_free_lump_sum_limit, 0.0),
            (cfg.pension_lump_sum_reduced_rate_limit, cfg.pension_lump_sum_reduced_rate),
            (None, cfg.pension_lump_sum_marginal_rate),
        ),
    )


def arf_minimum_drawdown_pct(
    age: int, total_arf_value: float, tax_config: TaxConfig | None = None
) -> float:
    """Mandatory ARF drawdown percentage for the year. 0 below age 60."""
    cfg = _config(tax_config)
    if age < 60:
        return 0.0
    if age < 70:
        return cfg.arf_min_drawdown_60_69
    if total_arf_value > cfg.arf_large_fund_threshold:
        return cfg.arf_min_drawdown_large_fund
    return cfg.arf_min_drawdown_70_plus
