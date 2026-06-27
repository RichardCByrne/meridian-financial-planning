"""TaxConfig dataclass — single source of truth for tax-rule constants.

Every tax-aware function in `engine/` accepts a `tax_config: TaxConfig`
parameter so a plan can pin its own jurisdiction / year / scenario-tweaked
ruleset. The seeded `IRELAND_2026_OFFICIAL` instance lives in
`config/tax_ie_2026.py` and is the default when no per-plan config is set.

Storage maps cleanly to/from a JSON dict via `to_dict` / `from_dict` so the
ORM layer can park the whole config in a single JSON column.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class FilingStatus:
    """How a Person files for the year. Drives band and credit selection."""

    married: bool = False
    is_two_income_couple: bool = False
    is_single_parent: bool = False
    is_paye_employee: bool = True  # vs self-employed
    home_carer: bool = False
    age: int = 35
    claims_rent_credit: bool = False
    # Euro value of medical-insurance relief due on employer-paid (BIK) premiums.
    # Computed per-person by the simulator (20% of premium, capped per adult/
    # child) and applied as a tax credit. Defaults to 0 for filers with no BIK.
    medical_insurance_relief: float = 0.0


@dataclass(frozen=True)
class TaxBreakdown:
    gross_income: float
    income_tax: float
    usc: float
    prsi: float
    total_tax: float
    net_income: float
    band_used: str
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TaxConfig:
    """All tunable tax constants for one year/jurisdiction."""

    name: str
    tax_year: int

    # Income tax
    standard_rate: float
    higher_rate: float
    srco_single: float
    srco_married_one_income: float
    srco_married_two_income_max: float
    srco_single_parent: float

    # Tax credits
    credit_personal_single: float
    credit_personal_married: float
    credit_paye_employee: float
    credit_earned_income: float
    credit_single_parent: float
    credit_home_carer: float

    # USC
    usc_exemption_threshold: float
    # Bands as list of (upper_bound|None, rate). `None` represents the open-ended top band.
    usc_bands: tuple[tuple[float | None, float], ...]

    # PRSI
    prsi_employee_rate: float
    prsi_self_employed_rate: float
    prsi_weekly_income_threshold: float
    prsi_min_annual: float

    # CGT / DIRT / ETF exit tax
    cgt_rate: float
    cgt_annual_exemption: float
    dirt_rate: float
    etf_exit_tax_rate: float
    etf_deemed_disposal_years: int

    # Pensions
    pension_earnings_cap: float
    # Age thresholds: [(max_age_inclusive, pct), ...]
    pension_contribution_limits_by_age: tuple[tuple[int, float], ...]
    pension_tax_free_lump_sum_limit: float
    pension_lump_sum_reduced_rate_limit: float
    pension_lump_sum_reduced_rate: float
    pension_lump_sum_marginal_rate: float
    standard_fund_threshold: float
    arf_min_drawdown_60_69: float
    arf_min_drawdown_70_plus: float
    arf_min_drawdown_large_fund: float
    arf_large_fund_threshold: float

    # CAT (used by Phase 12 inheritance work)
    cat_rate: float
    cat_group_thresholds: tuple[tuple[str, float], ...]  # (group, threshold)

    # Phase 14 additions — defaulted so existing TaxConfig(...) call sites that
    # don't pass them still construct cleanly (and the JSON migration path in
    # `from_dict` substitutes the seeded defaults for older payloads).
    # Rent tax credit (Budget 2023, €1,000/yr from 2024); doubled for jointly-
    # assessed married filers because each spouse can claim independently.
    credit_rent: float = 1_000.0
    # Age tax credit (Revenue.ie). Applies from age 65; €245 single / €490 married.
    credit_age_single: float = 245.0
    credit_age_married: float = 490.0
    age_credit_threshold_age: int = 65

    # Child Benefit (tax-free social welfare payment to the primary carer of a
    # child under 18). 2026 base rate: €140 / month per child. Escalation rate
    # is a long-run geometric mean from 2002 (€117.60) to 2026 (€140), ≈ 0.73%
    # — Child Benefit has been flat at €140 since 2016 but moved with Budget
    # decisions before that. 0.0075 keeps projections honest without assuming
    # CPI-style indexation that has never materialised.
    child_benefit_monthly: float = 140.0
    child_benefit_escalation: float = 0.0075
    child_benefit_age_limit: int = 18

    # Child education-stage age boundaries (Irish norms). Used by the simulator
    # to age-gate per-child rearing costs (see the Child cost fields). Childcare/
    # pre-school runs from birth until primary start; primary until secondary
    # start; secondary until secondary end. Third-level costs are NOT modelled
    # here — users represent college via an `education` goal instead. Everyday
    # costs (food/clothes) run from birth until secondary end.
    child_primary_start_age: int = 5
    child_secondary_start_age: int = 13
    child_secondary_end_age: int = 18

    # Benefit-in-kind (BIK). Cash-equivalent rates for non-cash perks an
    # employer provides; the cash equivalent is charged to IT/USC/PRSI as
    # notional pay. See `engine/bik_ie.py`.
    #   - Medical insurance: when the employer pays the premium, tax relief at
    #     source is not granted, so the employee claims 20% relief capped at
    #     €1,000/adult and €500/child.
    #   - Company car: cash equivalent = OMV × percentage. The 2023+ regime
    #     bands this by CO2 emissions and business mileage (≈6%–37.5%); we use a
    #     single mid-band default (22.5%) the user can override per benefit.
    #   - Company van: flat 8% of OMV.
    #   - Preferential loan: BIK = balance × (specified rate − rate charged).
    #     Specified rates are 4% for qualifying home loans, 13.5% otherwise.
    medical_insurance_relief_rate: float = 0.20
    medical_insurance_relief_cap_adult: float = 1_000.0
    medical_insurance_relief_cap_child: float = 500.0
    bik_company_car_default_rate: float = 0.225
    bik_company_van_rate: float = 0.08
    bik_preferential_loan_rate_qualifying: float = 0.04
    bik_preferential_loan_rate_other: float = 0.135

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable representation. Tuples become lists."""
        d = asdict(self)
        # asdict already converts tuples to lists for JSON. No further work needed.
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaxConfig":
        """Inverse of to_dict. Tolerates extra keys (forward-compat) and missing
        ones (we substitute the official seed's value)."""
        from app.config.tax_ie_2026 import IRELAND_2026_OFFICIAL  # local import: cycle

        defaults = asdict(IRELAND_2026_OFFICIAL)
        merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}

        # Re-tuple the list fields so the dataclass stays frozen+hashable.
        merged["usc_bands"] = tuple(
            (None if b[0] is None else float(b[0]), float(b[1])) for b in merged["usc_bands"]
        )
        merged["pension_contribution_limits_by_age"] = tuple(
            (int(a), float(p)) for (a, p) in merged["pension_contribution_limits_by_age"]
        )
        merged["cat_group_thresholds"] = tuple(
            (str(g), float(t)) for (g, t) in merged["cat_group_thresholds"]
        )
        return cls(**merged)

    def with_overrides(self, **kwargs: Any) -> "TaxConfig":
        """Return a copy with the given fields replaced. Used by tests + the
        scenario layer to tweak a config without mutating the official seed."""
        return replace(self, **kwargs)


def resolve(tax_config: "TaxConfig | None") -> "TaxConfig":
    """Return `tax_config` if non-None else the seeded official Ireland 2026 config."""
    if tax_config is not None:
        return tax_config
    # Local import: app.config.tax_ie_2026 imports TaxConfig from this module.
    from app.config.tax_ie_2026 import IRELAND_2026_OFFICIAL

    return IRELAND_2026_OFFICIAL
