"""Pure functions for Ireland benefit-in-kind (BIK) computation.

A benefit-in-kind is a non-cash perk an employer provides (employer-paid
medical insurance, a company car/van, a preferential loan, etc.). Irish
Revenue treats the *cash equivalent* of the benefit as notional pay: it is
charged to income tax, USC and PRSI through payroll, but the employee never
receives the money as cash and the household never pays for it (the employer
does). The net effect is that take-home cash falls by the tax on the benefit.

This module turns a benefit description into its taxable cash equivalent, per
benefit kind, plus the special medical-insurance relief an employee may claim
when the *employer* pays the premium (tax relief at source is not granted in
that case, so the 20% relief — capped per adult/child — is claimed instead).

No DB, no globals, no I/O — primitives in, euros out. Easy to unit-test.

NOT TAX ADVICE.
"""

from __future__ import annotations

from app.engine.tax_config import TaxConfig, resolve as _config

# Recognised BIK kinds. `other` is the catch-all flat cash-equivalent benefit.
BIK_KINDS: tuple[str, ...] = (
    "medical_insurance",
    "company_car",
    "company_van",
    "preferential_loan",
    "other",
)


def cash_equivalent(
    *,
    kind: str,
    amount: float = 0.0,
    omv: float = 0.0,
    rate: float = 0.0,
    loan_is_qualifying: bool = False,
    tax_config: TaxConfig | None = None,
) -> float:
    """Taxable cash equivalent (notional pay) of one benefit, by `kind`.

    - ``medical_insurance`` / ``other``: `amount` is the cash equivalent
      directly (the gross premium the employer pays, or any flat benefit value).
    - ``company_car``: `omv` × `rate`, where `rate` is the BIK percentage of
      Original Market Value (defaults to the config's mid-band rate when 0).
      Falls back to `amount` when no OMV is given.
    - ``company_van``: `omv` × the statutory van rate; falls back to `amount`.
    - ``preferential_loan``: `amount` is the outstanding loan balance and `rate`
      is the interest rate the employer actually charges. The BIK is the
      shortfall against the statutory specified rate (qualifying home-loan rate
      vs the higher general rate), i.e. balance × max(0, specified − charged).
    """
    cfg = _config(tax_config)

    if kind == "company_car":
        if omv > 0:
            pct = rate if rate > 0 else cfg.bik_company_car_default_rate
            return max(0.0, omv * pct)
        return max(0.0, amount)

    if kind == "company_van":
        if omv > 0:
            return max(0.0, omv * cfg.bik_company_van_rate)
        return max(0.0, amount)

    if kind == "preferential_loan":
        specified = (
            cfg.bik_preferential_loan_rate_qualifying
            if loan_is_qualifying
            else cfg.bik_preferential_loan_rate_other
        )
        return max(0.0, amount) * max(0.0, specified - rate)

    # medical_insurance / other / anything unrecognised — treat `amount` as the
    # cash equivalent so a bad kind never silently zeroes a real benefit.
    return max(0.0, amount)


def medical_insurance_relief(
    premium: float,
    adults: int,
    children: int,
    tax_config: TaxConfig | None = None,
) -> float:
    """Medical-insurance tax relief due when the employer pays the premium.

    Revenue gives 20% relief on the premium, capped at €1,000 per adult and
    €500 per child. Normally granted at source (TRS) when the individual pays;
    when the *employer* pays it is not, so the employee claims it as a credit.
    Returns the euro credit (0 if no premium).
    """
    if premium <= 0:
        return 0.0
    cfg = _config(tax_config)
    cap = (
        max(0, adults) * cfg.medical_insurance_relief_cap_adult
        + max(0, children) * cfg.medical_insurance_relief_cap_child
    )
    return cfg.medical_insurance_relief_rate * min(premium, cap)
