"""Pure functions for Ireland income tax / USC / PRSI computation.

The functions here take primitives (and a `FilingStatus`) and return a
`TaxBreakdown`. Tax-rule numbers come from a `TaxConfig` argument that
defaults to `IRELAND_2026_OFFICIAL` for back-compat with pre-Phase-11 callers.
No DB, no globals, no I/O — easy to unit-test.

Phase 11 introduced the `tax_config` parameter so a plan can pin its own
ruleset (e.g. forecast Budget 2027 by editing the official seed).
"""

from __future__ import annotations

from collections.abc import Iterable

from app.engine.tax_config import FilingStatus, TaxBreakdown, TaxConfig, resolve as _config


def progressive_tax(
    amount: float, bands: Iterable[tuple[float | None, float]]
) -> float:
    """Apply progressive bands `(upper, rate)` to `amount`.

    `upper=None` means the open-ended top band. Slices below `amount` are
    taxed at their band's rate; the slice straddling `amount` is taxed only
    on the portion below it. Used for USC and pension lump-sum tax.
    """
    if amount <= 0:
        return 0.0
    tax = 0.0
    lower = 0.0
    for upper, rate in bands:
        top = amount if upper is None else min(amount, upper)
        tax += max(0.0, top - lower) * rate
        if upper is None or amount <= upper:
            return tax
        lower = upper
    return tax


def income_tax(
    gross: float, status: FilingStatus, tax_config: TaxConfig | None = None
) -> tuple[float, str]:
    """Return (tax_after_credits, band_label). Tax floored at zero."""
    if gross <= 0:
        return 0.0, "none"

    cfg = _config(tax_config)

    if status.married and not status.is_two_income_couple:
        srco = cfg.srco_married_one_income
        band = "married_one_income"
    elif status.is_single_parent:
        srco = cfg.srco_single_parent
        band = "single_parent"
    else:
        srco = cfg.srco_single
        band = "single"

    standard_band_used = min(gross, srco)
    higher_band_used = max(0.0, gross - srco)
    gross_tax = standard_band_used * cfg.standard_rate + higher_band_used * cfg.higher_rate

    credits = (
        cfg.credit_personal_married if status.married else cfg.credit_personal_single
    )
    if status.is_paye_employee:
        credits += cfg.credit_paye_employee
    else:
        credits += cfg.credit_earned_income
    if status.is_single_parent:
        credits += cfg.credit_single_parent
    if status.home_carer:
        credits += cfg.credit_home_carer
    if status.claims_rent_credit:
        # Married filers get 2× (each spouse's claim aggregated under joint assessment).
        credits += cfg.credit_rent * (2 if status.married else 1)
    if status.age >= cfg.age_credit_threshold_age:
        credits += cfg.credit_age_married if status.married else cfg.credit_age_single

    return max(0.0, gross_tax - credits), band


def usc(gross: float, tax_config: TaxConfig | None = None) -> float:
    """Universal Social Charge. Whole-income test for the exemption threshold."""
    cfg = _config(tax_config)
    if gross <= cfg.usc_exemption_threshold:
        return 0.0
    return progressive_tax(gross, cfg.usc_bands)


def prsi(
    gross: float,
    *,
    is_paye: bool,
    weekly_average: float | None = None,
    tax_config: TaxConfig | None = None,
) -> float:
    """PRSI on earned income.

    `weekly_average` is optional; if provided and below the Class A threshold,
    PAYE employees pay zero PRSI. For projection purposes we approximate weekly
    as gross/52 unless overridden.
    """
    if gross <= 0:
        return 0.0

    cfg = _config(tax_config)

    if is_paye:
        weekly = weekly_average if weekly_average is not None else gross / 52
        if weekly < cfg.prsi_weekly_income_threshold:
            return 0.0
        return gross * cfg.prsi_employee_rate

    # Self-employed: minimum annual contribution
    return max(cfg.prsi_min_annual, gross * cfg.prsi_self_employed_rate)


def compute(
    gross_income: float, status: FilingStatus, tax_config: TaxConfig | None = None
) -> TaxBreakdown:
    """End-to-end: gross earnings -> income tax + USC + PRSI -> net."""
    cfg = _config(tax_config)
    it, band = income_tax(gross_income, status, cfg)
    u = usc(gross_income, cfg)
    p = prsi(gross_income, is_paye=status.is_paye_employee, tax_config=cfg)
    total = it + u + p
    return TaxBreakdown(
        gross_income=gross_income,
        income_tax=round(it, 2),
        usc=round(u, 2),
        prsi=round(p, 2),
        total_tax=round(total, 2),
        net_income=round(gross_income - total, 2),
        band_used=band,
    )
