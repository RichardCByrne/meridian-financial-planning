"""Asset liquidation order and disposal-tax-aware withdrawal.

Pure functions — no DB, no HTTP, no simulator state. Imported by
`engine/simulator.py` when a year ends in shortfall and assets must be drawn
down to fund the gap.

Default order is taxable-first (cash → deposits) → unwrapped investments →
ETFs → BTL property → primary residence. Pension wrappers are intentionally
excluded; ARF drawdown is driven by retirement-age logic in the simulator,
not the shortfall-funding path.

Disposal-tax rates come from a `TaxConfig` so a per-plan ruleset can edit
CGT or ETF exit tax independently of the seeded official.
"""

from __future__ import annotations

from app.engine.tax_config import TaxConfig, resolve as _resolve_config

LIQUIDATION_ORDER: tuple[str, ...] = (
    "cash",
    "deposit",
    "investment_unwrapped",
    "etf_fund",
    "property_btl",
    "property_primary",
)


def disposal_tax_rate(kind: str, tax_config: TaxConfig | None = None) -> float:
    """Per-asset-kind disposal tax rate. Returns 0.0 if no disposal tax applies.

    - cash / deposit: no disposal tax (DIRT applies on deposit interest, handled
      at growth time, not on withdrawal).
    - investment_unwrapped: CGT (33% by default) on the realised gain. The
      annual €1,270 exemption is applied later in the simulator after summing
      all unwrapped disposals for the year.
    - etf_fund: ETF exit tax (41% by default) on the realised gain.
    - property: kept tax-free in this iteration. Primary residence is CGT-exempt
      in Ireland; BTL would normally attract CGT but is deferred to a later phase.
    """
    tax_config = _resolve_config(tax_config)
    if kind == "investment_unwrapped":
        return tax_config.cgt_rate
    if kind == "etf_fund":
        return tax_config.etf_exit_tax_rate
    return 0.0


def withdraw_with_tax(
    balance: float,
    cost_basis: float,
    need_net: float,
    rate: float,
) -> tuple[float, float, float, float]:
    """Pull `need_net` net of disposal tax from a position with cost basis pro-rata.

    Returns (gross_withdrawn, new_balance, new_basis, tax). If insufficient, returns
    everything available — caller checks `gross_withdrawn`.
    """
    if balance <= 0 or need_net <= 0:
        return 0.0, balance, cost_basis, 0.0
    if rate <= 0 or balance <= cost_basis:
        # No gain (or no tax kind) — straight withdrawal.
        gross = min(balance, need_net)
        new_basis = cost_basis * (1.0 - gross / balance) if balance > 0 else 0.0
        return gross, balance - gross, max(new_basis, 0.0), 0.0

    gain_per_euro = 1.0 - cost_basis / balance  # fraction of each withdrawn € that is gain
    effective_net_per_gross = 1.0 - rate * gain_per_euro
    if effective_net_per_gross <= 0:
        # Pathological — shouldn't happen with rate <1, gain_per_euro <=1.
        return 0.0, balance, cost_basis, 0.0

    gross_needed = need_net / effective_net_per_gross
    if gross_needed >= balance:
        # Liquidate fully.
        gain = balance - cost_basis
        tax = gain * rate
        return balance, 0.0, 0.0, tax
    gain = gross_needed * gain_per_euro
    tax = gain * rate
    new_basis = cost_basis * (1.0 - gross_needed / balance)
    return gross_needed, balance - gross_needed, max(new_basis, 0.0), tax
