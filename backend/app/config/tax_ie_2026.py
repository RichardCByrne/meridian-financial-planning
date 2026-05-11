"""Ireland tax configuration for the year 2026 — seeded `TaxConfig` instance.

This module's job is to construct `IRELAND_2026_OFFICIAL`, the canonical
`TaxConfig` for Ireland 2026. Engine functions accept a `tax_config` argument
that defaults to this when nothing is passed (so existing callers keep
working). Per-plan custom configs are stored in the database (Phase 11) and
are passed in explicitly by the projections router.

Sources: Budget 2026 (Oct 2025), Revenue.ie, KPMG / BDO / Grant Thornton
Budget 2026 summaries.

NOT TAX ADVICE.
"""

from app.engine.tax_config import FilingStatus, TaxBreakdown, TaxConfig

IRELAND_2026_OFFICIAL = TaxConfig(
    name="Ireland 2026 (official)",
    tax_year=2026,

    # ----- Income tax bands -----
    standard_rate=0.20,
    higher_rate=0.40,
    srco_single=44_000.0,
    srco_married_one_income=53_000.0,
    srco_married_two_income_max=88_000.0,
    srco_single_parent=48_000.0,

    # ----- Tax credits -----
    credit_personal_single=2_000.0,
    credit_personal_married=4_000.0,
    credit_paye_employee=2_000.0,
    credit_earned_income=2_000.0,
    credit_single_parent=1_900.0,
    credit_home_carer=1_950.0,
    credit_rent=1_000.0,
    credit_age_single=245.0,
    credit_age_married=490.0,
    age_credit_threshold_age=65,

    # ----- USC -----
    usc_exemption_threshold=13_000.0,
    usc_bands=(
        (12_012.0, 0.005),
        (28_700.0, 0.02),
        (70_044.0, 0.03),
        (None, 0.08),
    ),

    # ----- PRSI (2026 blended Jan–Sep 4.20% / Oct–Dec 4.35%) -----
    prsi_employee_rate=0.042375,
    prsi_self_employed_rate=0.042375,
    prsi_weekly_income_threshold=352.0,
    prsi_min_annual=500.0,

    # ----- CGT / DIRT / ETF -----
    cgt_rate=0.33,
    cgt_annual_exemption=1_270.0,
    dirt_rate=0.33,
    etf_exit_tax_rate=0.41,
    etf_deemed_disposal_years=8,

    # ----- Pensions -----
    pension_earnings_cap=115_000.0,
    pension_contribution_limits_by_age=(
        (29, 0.15),
        (39, 0.20),
        (49, 0.25),
        (54, 0.30),
        (59, 0.35),
        (200, 0.40),
    ),
    pension_tax_free_lump_sum_limit=200_000.0,
    pension_lump_sum_reduced_rate_limit=500_000.0,
    pension_lump_sum_reduced_rate=0.20,
    pension_lump_sum_marginal_rate=0.40,
    standard_fund_threshold=2_000_000.0,
    arf_min_drawdown_60_69=0.04,
    arf_min_drawdown_70_plus=0.05,
    arf_min_drawdown_large_fund=0.06,
    arf_large_fund_threshold=2_000_000.0,

    # ----- CAT (Capital Acquisitions Tax) — used by Phase 12 -----
    cat_rate=0.33,
    cat_group_thresholds=(
        ("A", 400_000.0),  # child / parent
        ("B", 40_000.0),
        ("C", 20_000.0),
    ),
)


# ---------------------------------------------------------------------------
# Back-compat: keep the historical module-level constants as references to the
# official seed. Engine code is being migrated to take a `tax_config` parameter
# and will stop using these. Tests that import the constants directly continue
# to work unchanged.
# ---------------------------------------------------------------------------

TAX_YEAR = IRELAND_2026_OFFICIAL.tax_year

STANDARD_RATE = IRELAND_2026_OFFICIAL.standard_rate
HIGHER_RATE = IRELAND_2026_OFFICIAL.higher_rate
SRCO_SINGLE = IRELAND_2026_OFFICIAL.srco_single
SRCO_MARRIED_ONE_INCOME = IRELAND_2026_OFFICIAL.srco_married_one_income
SRCO_MARRIED_TWO_INCOME_MAX = IRELAND_2026_OFFICIAL.srco_married_two_income_max
SRCO_SINGLE_PARENT = IRELAND_2026_OFFICIAL.srco_single_parent

CREDIT_PERSONAL_SINGLE = IRELAND_2026_OFFICIAL.credit_personal_single
CREDIT_PERSONAL_MARRIED = IRELAND_2026_OFFICIAL.credit_personal_married
CREDIT_PAYE_EMPLOYEE = IRELAND_2026_OFFICIAL.credit_paye_employee
CREDIT_EARNED_INCOME = IRELAND_2026_OFFICIAL.credit_earned_income
CREDIT_SINGLE_PARENT = IRELAND_2026_OFFICIAL.credit_single_parent
CREDIT_HOME_CARER = IRELAND_2026_OFFICIAL.credit_home_carer

USC_EXEMPTION_THRESHOLD = IRELAND_2026_OFFICIAL.usc_exemption_threshold
USC_BANDS = list(IRELAND_2026_OFFICIAL.usc_bands)

PRSI_EMPLOYEE_RATE = IRELAND_2026_OFFICIAL.prsi_employee_rate
PRSI_SELF_EMPLOYED_RATE = IRELAND_2026_OFFICIAL.prsi_self_employed_rate
PRSI_WEEKLY_INCOME_THRESHOLD = IRELAND_2026_OFFICIAL.prsi_weekly_income_threshold
PRSI_MIN_ANNUAL = IRELAND_2026_OFFICIAL.prsi_min_annual

CGT_RATE = IRELAND_2026_OFFICIAL.cgt_rate
CGT_ANNUAL_EXEMPTION = IRELAND_2026_OFFICIAL.cgt_annual_exemption
DIRT_RATE = IRELAND_2026_OFFICIAL.dirt_rate
ETF_EXIT_TAX_RATE = IRELAND_2026_OFFICIAL.etf_exit_tax_rate
ETF_DEEMED_DISPOSAL_YEARS = IRELAND_2026_OFFICIAL.etf_deemed_disposal_years

PENSION_EARNINGS_CAP = IRELAND_2026_OFFICIAL.pension_earnings_cap
PENSION_CONTRIBUTION_LIMITS_BY_AGE = list(IRELAND_2026_OFFICIAL.pension_contribution_limits_by_age)
PENSION_TAX_FREE_LUMP_SUM_LIMIT = IRELAND_2026_OFFICIAL.pension_tax_free_lump_sum_limit
PENSION_LUMP_SUM_REDUCED_RATE_LIMIT = IRELAND_2026_OFFICIAL.pension_lump_sum_reduced_rate_limit
PENSION_LUMP_SUM_REDUCED_RATE = IRELAND_2026_OFFICIAL.pension_lump_sum_reduced_rate
STANDARD_FUND_THRESHOLD = IRELAND_2026_OFFICIAL.standard_fund_threshold

CAT_RATE = IRELAND_2026_OFFICIAL.cat_rate
CAT_GROUP_THRESHOLDS = dict(IRELAND_2026_OFFICIAL.cat_group_thresholds)


# Re-export these so the existing `from app.config.tax_ie_2026 import FilingStatus` path keeps working.
__all__ = [
    "IRELAND_2026_OFFICIAL",
    "FilingStatus",
    "TaxBreakdown",
    "TAX_YEAR",
    "STANDARD_RATE",
    "HIGHER_RATE",
    "SRCO_SINGLE",
    "SRCO_MARRIED_ONE_INCOME",
    "SRCO_MARRIED_TWO_INCOME_MAX",
    "SRCO_SINGLE_PARENT",
    "CREDIT_PERSONAL_SINGLE",
    "CREDIT_PERSONAL_MARRIED",
    "CREDIT_PAYE_EMPLOYEE",
    "CREDIT_EARNED_INCOME",
    "CREDIT_SINGLE_PARENT",
    "CREDIT_HOME_CARER",
    "USC_EXEMPTION_THRESHOLD",
    "USC_BANDS",
    "PRSI_EMPLOYEE_RATE",
    "PRSI_SELF_EMPLOYED_RATE",
    "PRSI_WEEKLY_INCOME_THRESHOLD",
    "PRSI_MIN_ANNUAL",
    "CGT_RATE",
    "CGT_ANNUAL_EXEMPTION",
    "DIRT_RATE",
    "ETF_EXIT_TAX_RATE",
    "ETF_DEEMED_DISPOSAL_YEARS",
    "PENSION_EARNINGS_CAP",
    "PENSION_CONTRIBUTION_LIMITS_BY_AGE",
    "PENSION_TAX_FREE_LUMP_SUM_LIMIT",
    "PENSION_LUMP_SUM_REDUCED_RATE_LIMIT",
    "PENSION_LUMP_SUM_REDUCED_RATE",
    "STANDARD_FUND_THRESHOLD",
    "CAT_RATE",
    "CAT_GROUP_THRESHOLDS",
]
