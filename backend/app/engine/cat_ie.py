"""Capital Acquisitions Tax (CAT) engine — Ireland.

CAT is the gift and inheritance tax. It applies to cumulative lifetime
receipts: once a beneficiary has received gifts/inheritances that exceed
their group threshold (aggregated across all donors in that group), all
further receipts are taxed at `tax_config.cat_rate`.

Groups (Ireland 2026):
  A — children, adoptive children, parents in certain cases: €400,000
  B — linear ancestors/descendants (excl. A), siblings, half-siblings: €40,000
  C — all others: €20,000
  exempt — spouse / civil partner: no CAT regardless of amount

NOT TAX ADVICE.
"""

from __future__ import annotations

from app.engine.tax_config import TaxConfig


def group_threshold(group: str, tax_config: TaxConfig) -> float:
    """Return the lifetime exemption threshold for `group` from the config."""
    return dict(tax_config.cat_group_thresholds).get(group, 0.0)


def compute_cat(
    gross_inheritance: float,
    group: str,
    prior_lifetime_receipts: float,
    tax_config: TaxConfig,
) -> float:
    """Return CAT owed on `gross_inheritance`.

    `prior_lifetime_receipts` is the total of previous gifts/inheritances
    already received by this beneficiary from all donors in the same group
    (the Irish threshold works on a cumulative per-beneficiary basis).

    Returns 0 for group "exempt" regardless of amount.
    """
    if group == "exempt":
        return 0.0
    threshold = group_threshold(group, tax_config)
    total = prior_lifetime_receipts + gross_inheritance
    taxable_total = max(0.0, total - threshold)
    already_above = max(0.0, prior_lifetime_receipts - threshold)
    marginal_taxable = max(0.0, taxable_total - already_above)
    return round(marginal_taxable * tax_config.cat_rate, 2)


def apply_section72(cat_due: float, policy_payout: float) -> tuple[float, float]:
    """Apply a Revenue-approved Section 72 life-assurance policy against a CAT
    bill. Proceeds used to pay the inheritance CAT are exempt from CAT; the
    relief caps at the CAT due. Any proceeds beyond the bill are excess (in
    reality themselves CAT-able — the caller decides what to do with it).

    Returns (cat_after_relief, excess).
    """
    cat_due = max(0.0, cat_due)
    payout = max(0.0, policy_payout)
    relief = min(cat_due, payout)
    return round(cat_due - relief, 2), round(payout - relief, 2)
