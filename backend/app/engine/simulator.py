"""Year-by-year financial plan simulator.

Pure function. Takes domain dataclasses (not ORM rows), returns a list of
YearRow records spanning `base_year` to `base_year + projection_years - 1`.

Per-year flow: age people → grow assets → accrue income → compute tax →
sum expenses → fund any shortfall by liquidating assets (order in
`engine.liquidation`) → amortise liabilities → resolve goal status → emit
YearRow.

Tax rules: `engine.tax_ie` (income tax, USC, PRSI), `engine.pension_ie`
(contribution caps, lump-sum bands, ARF imputed drawdown). CGT and ETF
exit tax are applied at disposal via `engine.liquidation.withdraw_with_tax`.
Scenario overrides are applied to PlanInput before simulate() — see
`engine.scenario.apply_overrides`.
"""

import math
from dataclasses import dataclass, field, replace
from datetime import date

from app.engine import bik_ie, cat_ie, pension_ie, tax_ie
from app.engine.liquidation import (
    LIQUID_ASSET_KINDS,
    LIQUIDATION_ORDER,
    disposal_tax_rate as _disposal_tax_rate,
    withdraw_with_tax as _withdraw_with_tax,
)
from app.engine.tax_config import FilingStatus, TaxConfig, resolve as _resolve_tax_config


@dataclass
class PersonInput:
    id: int
    name: str
    dob: date
    is_primary: bool
    life_expectancy: int
    retirement_age: int | None = None
    claims_rent_credit: bool = False
    # Fraction of pension pot taken as lump sum at retirement. Irish rules cap
    # this at 25%; anything below leaves more in the ARF (more PAYE on drawdown,
    # bigger compounding base). Default 0.25 = previous hardcoded behaviour.
    lump_sum_pct: float = 0.25
    # PRSI contribution history seeded at the start of the projection.
    # The Total Contributions Approach (TCA) needs lifetime weeks to scale the
    # state pension at retirement; the engine accumulates +52/yr while the
    # person has any PRSI-paying income, but pre-base-year history is the
    # caller's responsibility. Default 2080 = full TCA cap, matching legacy
    # behaviour where everyone got the full state_pension_annual_amount.
    prsi_weeks_at_base_year: int = 2080
    # HomeCaring weeks already accrued before the projection starts. Capped
    # at 1,040 (20 years) by the Department of Social Protection.
    homecaring_weeks_at_base_year: int = 0
    # Voluntary ARF drawdown rate. None = use statutory minimum only (4%/5%/6%).
    # When set, engine draws max(statutory_minimum, target) each post-retirement
    # year. Lets users model "I want 6% drawdown" or back-solve from a target
    # monthly spend. Range [0.0, 1.0]. Only used when pension_option == "arf".
    arf_target_drawdown_pct: float | None = None
    # Tax-optimal decumulation: when True, the ARF is drawn each post-retirement
    # year up to the top of the standard-rate band (filling cheap 20% headroom
    # left by other income) rather than just the statutory minimum — smoothing
    # marginal rates across retirement. Still respects the statutory minimum as a
    # floor and never draws more than the pot. Only used when pension_option ==
    # "arf". Default False = previous behaviour.
    arf_band_fill: bool = False
    # What to do with the pension pot remaining after the tax-free lump sum at
    # retirement. Irish options:
    #   "arf"               — invest in an ARF, draw it down over time (default).
    #   "annuity"           — buy a lifetime annuity: pot is converted into a
    #                         level annual income (annuity_rate × pot) and leaves
    #                         the estate. Income is taxed as PAYE, PRSI-exempt.
    #   "taxable_lump_sum"  — take the whole remainder as cash in the retirement
    #                         year, taxed at the marginal income-tax rate.
    pension_option: str = "arf"
    # Annual annuity income as a fraction of the annuitised pot. Only used when
    # pension_option == "annuity". ~4% is a typical Irish level-annuity rate.
    annuity_rate: float = 0.04
    # Optional planned/what-if death year. When set and earlier than the natural
    # life_expectancy year (dob.year + life_expectancy), the person dies then:
    # income/BIK stop, their estate transfers to survivors (CAT via the existing
    # bequest machinery) and any in-force term-life policy pays out. None = die
    # at life_expectancy as before. Scenario-patchable (protection what-ifs).
    death_year: int | None = None


@dataclass
class IncomeInput:
    id: int
    person_id: int
    kind: str
    name: str
    gross_amount: float
    start_year: int
    end_year: int | None
    escalation_rate: float
    pays_prsi: bool
    pays_usc: bool
    pension_contribution_pct: float = 0.0
    employer_pension_contribution_pct: float = 0.0
    # An employment bonus. Taxed as normal income, but employment-related, so it
    # stops at retirement like salary even when modelled with a passive `kind`
    # (the one-click bonus uses kind="other") and left with an open end_year.
    is_bonus: bool = False
    # Rental income only: allowable-expenses fraction of gross rent and the
    # furnishings value for the wear-and-tear capital allowance. Taxable rental
    # profit = gross − gross×rental_expenses_pct − wear_and_tear. 0 = gross.
    rental_expenses_pct: float = 0.0
    furnishings_value: float = 0.0


@dataclass
class BenefitInput:
    """An employer-provided benefit-in-kind charged to the employee as notional
    pay (IT + USC + PRSI) but never received as cash and never paid for by the
    household. See `engine.bik_ie` for the per-kind cash-equivalent calculation.

    Field meaning depends on `kind`:
      - medical_insurance / other → `amount` is the cash equivalent (premium).
      - company_car / company_van → `omv` × rate (car uses `rate`, default mid
        band; van uses the statutory rate). Falls back to `amount` if omv == 0.
      - preferential_loan → `amount` is the loan balance, `rate` the rate the
        employer charges; BIK = balance × (specified − charged).
    `relief_adults` / `relief_children` size the medical-insurance relief cap.
    """
    id: int
    person_id: int
    kind: str
    name: str
    start_year: int
    end_year: int | None
    escalation_rate: float = 0.0
    amount: float = 0.0
    omv: float = 0.0
    rate: float = 0.0
    loan_is_qualifying: bool = False
    relief_adults: int = 1
    relief_children: int = 0


@dataclass
class ExpenseInput:
    id: int
    name: str
    category: str
    amount: float
    start_year: int
    end_year: int | None
    escalation_rate: float


@dataclass
class AssetInput:
    id: int
    name: str
    kind: str
    value: float
    growth_rate: float
    cost_basis: float
    acquired_year: int | None = None
    owner_person_id: int | None = None
    annual_contribution: float = 0.0
    contribution_pct_of_net_income: float = 0.0
    contribution_pct_of_gross_income: float = 0.0
    contribution_start_year: int | None = None
    contribution_end_year: int | None = None
    avc_annual: float = 0.0
    avc_pct_of_gross: float = 0.0
    # Planned property/asset transactions (Phase 1). `purchase_year` in the
    # future gates the asset: it holds no value and doesn't grow until then,
    # when `value` becomes its balance and `deposit` is paid out of cash (the
    # rest of the price is a separately-added mortgage). `disposal_year`
    # triggers a deliberate full sale — net proceeds (after any disposal tax)
    # land in cash. Both None = today's behaviour (owned from base year, never
    # deliberately sold). Distinct from `acquired_year`, which is only the ETF
    # deemed-disposal clock.
    purchase_year: int | None = None
    deposit: float = 0.0
    disposal_year: int | None = None
    # Phase 2. `linked_liability_id` ties this asset to the mortgage financing it
    # — a planned disposal settles that liability's outstanding balance out of the
    # sale proceeds and stops its amortisation. `stamp_duty_pct` is charged on the
    # purchase price (paid from cash on purchase); `selling_cost_pct` (agent/legal
    # fees) is taken off the sale proceeds. BTL disposals also attract CGT on the
    # gain net of selling costs; a primary residence stays CGT-exempt.
    linked_liability_id: int | None = None
    stamp_duty_pct: float = 0.0
    selling_cost_pct: float = 0.0
    # Total annual product charge (AMC + platform + adviser fee) as a fraction of
    # balance. Deducted from growth each year so the pot compounds net of charges.
    # 0.0 = no charge (previous behaviour).
    annual_charge_pct: float = 0.0


@dataclass
class LiabilityAdjustmentInput:
    id: int
    # "rate" → new annual rate (fraction); "overpayment" → new €/mo overpayment;
    # "lump_sum" → one-off € paid off capital in effective_year only.
    kind: str
    effective_year: int
    value: float


@dataclass
class LiabilityInput:
    id: int
    name: str
    kind: str
    principal: float
    interest_rate: float
    term_months: int
    start_year: int
    monthly_payment: float
    # Extra €/mo applied directly to capital. Shortens the loan term. Banks
    # typically allow ±10% of the contracted monthly_payment fee-free; we
    # don't model the breakage-fee threshold — out of scope for most users.
    monthly_overpayment: float = 0.0
    # Time-keyed rate steps / overpayment changes / lump sums (Voyant-style).
    adjustments: list[LiabilityAdjustmentInput] = field(default_factory=list)


@dataclass
class BequestInput:
    id: int
    from_person_id: int
    to_person_id: int | None  # None = external beneficiary (leaves plan)
    cat_group: str  # "A", "B", "C", "exempt"
    share_pct: float  # fraction of estate (0.0–1.0)


@dataclass
class LifePolicyInput:
    """Term-life protection policy on one person (the insured). While in force
    (start_year..end_year, end None = open-ended) the plan pays `premium_annual`
    out of cash; if the insured dies within the term, `sum_assured` pays out
    tax-free to survivors' cash. `kind` is reserved for future protection types
    but only "term_life" produces a payout today."""
    id: int
    person_id: int
    name: str
    sum_assured: float
    premium_annual: float
    start_year: int
    end_year: int | None = None
    kind: str = "term_life"


@dataclass
class DBPensionInput:
    """Defined-benefit / final-salary pension for one person. Pays a guaranteed
    annual income from normal_retirement_age = accrual_rate × service_years ×
    final_salary, indexed by revaluation_rate (deferment + in payment). Taxed as
    PAYE income, PRSI-exempt (like an ARF or annuity). An optional
    tax_free_lump_sum is paid to cash at retirement."""
    id: int
    person_id: int
    name: str
    accrual_rate: float
    service_years: float
    final_salary: float
    revaluation_rate: float = 0.0
    normal_retirement_age: int = 65
    tax_free_lump_sum: float = 0.0


@dataclass
class GoalInput:
    id: int
    kind: str
    name: str
    target_amount: float
    target_year: int
    linked_person_id: int | None = None


@dataclass
class ChildInput:
    id: int
    name: str
    dob: date
    # Person who receives the Child Benefit payment (typically the primary
    # carer). None = pay to the plan's primary person.
    primary_carer_id: int | None = None
    # Whether this child is counted in the projection. Always True for base-plan
    # children; a scenario can flip it to False to model a smaller family
    # (Child Benefit and all child-driven costs are skipped). Not persisted on
    # the ORM Child row — it only exists as a scenario override.
    active: bool = True
    # Per-child rearing costs (annual €, 0 = not modelled), age-gated against
    # dob using TaxConfig stage boundaries and escalated by the plan inflation
    # rate. See the engine step "Child-stage costs" and the ORM Child model.
    childcare_annual: float = 0.0
    primary_annual: float = 0.0
    secondary_annual: float = 0.0
    secondary_is_private: bool = False
    secondary_private_fee_annual: float = 0.0
    everyday_annual: float = 0.0


@dataclass
class AssumptionsInput:
    inflation_rate: float = 0.025
    default_growth_rate: float = 0.05
    property_growth_rate: float = 0.03
    earnings_growth: float = 0.03
    state_pension_age: int = 66
    state_pension_annual_amount: float = 15_563.0
    state_pension_escalation_rate: float = 0.015


@dataclass
class PlanInput:
    base_year: int
    projection_years: int
    people: list[PersonInput]
    incomes: list[IncomeInput]
    expenses: list[ExpenseInput]
    assets: list[AssetInput]
    assumptions: AssumptionsInput
    liabilities: list[LiabilityInput] = field(default_factory=list)
    goals: list[GoalInput] = field(default_factory=list)
    bequests: list[BequestInput] = field(default_factory=list)
    children: list[ChildInput] = field(default_factory=list)
    benefits: list[BenefitInput] = field(default_factory=list)
    life_policies: list[LifePolicyInput] = field(default_factory=list)
    db_pensions: list[DBPensionInput] = field(default_factory=list)
    # Tax-rule constants. None = use IRELAND_2026_OFFICIAL.
    tax_config: TaxConfig | None = None
    # Filing status override. None → auto (1 person → single, 2+ → married).
    # Explicit "cohabiting" forces single-band tax for both people, which is
    # how Irish Revenue actually treats unmarried couples.
    filing_status: str | None = None
    # Marriage event year. None = no change. If set, both people are taxed as a
    # jointly-assessed married couple (SRCO band transfer + married personal
    # credit) from this calendar year onward, regardless of `filing_status`;
    # earlier years keep the base status. Requires ≥2 people to have any effect.
    # This is the engine hook a scenario uses to model "getting married in year N".
    marriage_year: int | None = None


@dataclass
class PersonYear:
    person_id: int
    name: str
    age: int
    gross_income: float
    income_tax: float
    usc: float
    prsi: float
    net_income: float


@dataclass
class YearRow:
    year: int
    ages: dict[int, int]
    persons: list[PersonYear]
    gross_income_total: float
    income_by_kind: dict[str, float]
    total_tax: float
    income_tax: float
    usc: float
    prsi: float
    net_income_total: float
    expenses_total: float
    expenses_by_category: dict[str, float]
    surplus_or_shortfall: float
    asset_balances: dict[int, float]
    asset_balances_by_kind: dict[str, float]
    withdrawals_by_asset: dict[int, float]
    net_worth: float
    liability_balances: dict[int, float] = field(default_factory=dict)
    debt_outstanding: float = 0.0
    investment_tax: float = 0.0
    realised_gains: float = 0.0
    pension_contributions: float = 0.0
    employer_pension_contributions: float = 0.0
    pension_lump_sum: float = 0.0
    pension_lump_sum_tax: float = 0.0
    arf_drawdowns: float = 0.0
    state_pension_total: float = 0.0
    db_pension_total: float = 0.0
    goal_status: dict[int, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    cat_paid: float = 0.0
    estate_transfers: dict[int, float] = field(default_factory=dict)
    asset_contributions: float = 0.0
    had_shortfall: bool = False
    # Total taxable cash-equivalent of employer benefits-in-kind charged this
    # year (notional pay: taxed but not received as cash, not a household
    # expense). Reported separately so it doesn't double-count in cash gross.
    benefits_in_kind_total: float = 0.0
    # Net worth minus assets locked to a person's pre-retirement pension wrappers
    # (prsa / occupational_pension / avc). ARF balances are always accessible since
    # they only exist post-retirement and are drawn down automatically. Property,
    # cash, investments stay accessible regardless of age.
    accessible_net_worth: float = 0.0
    # Gross value of liquid assets only — cash, deposits, unwrapped investments
    # and ETFs (see `engine.liquidation.LIQUID_ASSET_KINDS`). Excludes property
    # (illiquid) and every pension/ARF (restricted), and is NOT netted against
    # debt. This is the figure goal affordability/achievability is graded
    # against: you shouldn't have to sell the house or raid a pension to hit a
    # target or fund a planned spend.
    liquid_assets: float = 0.0
    # Protection (term-life) figures. `protection_premiums_total` is the premiums
    # paid this year (already included in expenses_total). `life_cover_payout` is
    # any tax-free sum assured paid to survivors on a death this year.
    protection_premiums_total: float = 0.0
    life_cover_payout: float = 0.0
    # Capital shortfall: debt still outstanding that liquid assets can't clear
    # (max(0, debt_outstanding - liquid_assets)). Most useful in a death year —
    # shows whether survivors can at least clear the debts. 0 = fully covered.
    cover_gap: float = 0.0
    # CAT covered this year by a Section 72 policy on a deceased person (already
    # netted out of cat_paid). 0 when no approved policy paid out.
    section72_cat_relief: float = 0.0


def _age_in_year(dob: date, year: int) -> int:
    return year - dob.year


def _death_year_for(person: PersonInput) -> int:
    """The year the person dies: the earlier of an explicit death_year and the
    natural life_expectancy year (dob.year + life_expectancy). Equivalent to the
    old `age >= life_expectancy` trigger when death_year is None."""
    natural = person.dob.year + person.life_expectancy
    if person.death_year is not None:
        return min(natural, person.death_year)
    return natural


def _income_active(inc: IncomeInput, year: int) -> bool:
    if year < inc.start_year:
        return False
    if inc.end_year is not None and year > inc.end_year:
        return False
    return True


def _benefit_active(b: BenefitInput, year: int) -> bool:
    if year < b.start_year:
        return False
    if b.end_year is not None and year > b.end_year:
        return False
    return True


def _expense_active(e: ExpenseInput, year: int) -> bool:
    if e.category == "single_year":
        return year == e.start_year
    if year < e.start_year:
        return False
    if e.end_year is not None and year > e.end_year:
        return False
    return True


def _escalate(amount: float, rate: float, years_elapsed: int) -> float:
    if years_elapsed <= 0:
        return amount
    return amount * ((1.0 + rate) ** years_elapsed)


def _is_paye_kind(kind: str) -> bool:
    return kind in ("employment", "rental", "state_pension", "annuity", "private_pension_drawdown", "other")


def _filing_status_for_person(
    person: PersonInput,
    all_people: list[PersonInput],
    any_two_income: bool,
    plan_filing_status: str | None,
    *,
    age: int,
    is_paye_employee: bool,
    year: int,
    marriage_year: int | None = None,
) -> FilingStatus:
    # A marriage event flips the couple to jointly-assessed married from its
    # year onward, overriding the base filing status. Only meaningful for couples.
    married_by_event = (
        marriage_year is not None and year >= marriage_year and len(all_people) >= 2
    )
    if plan_filing_status == "married" or married_by_event:
        married = True
    elif plan_filing_status in ("single", "cohabiting"):
        # Cohabiting couples are taxed individually under Irish law — no SRCO
        # transfer, no married personal credit. The simulator treats each
        # person as `married=False` so they each get the single-rate band and
        # single personal credit.
        married = False
    else:
        # Auto: legacy heuristic — two-person plan → assume married.
        married = len(all_people) >= 2
    return FilingStatus(
        married=married,
        is_two_income_couple=married and any_two_income,
        is_paye_employee=is_paye_employee,
        age=age,
        claims_rent_credit=person.claims_rent_credit,
    )


def _amortise_year(
    balance: float,
    monthly_rate: float,
    monthly_payment: float,
    monthly_overpayment: float = 0.0,
) -> tuple[float, float, float]:
    """Run up to 12 monthly steps. Returns (new_balance, total_interest_paid, total_paid).

    `monthly_overpayment` is extra capital paid each month on top of the
    contracted payment. Negative values are clamped to 0 — the engine does
    not model underpayment / payment holidays.

    Loan may pay off mid-year — closed-form geometric solution is unsafe across
    that boundary, so iterate.
    """
    extra = max(0.0, monthly_overpayment)
    interest_paid = 0.0
    paid = 0.0
    for _ in range(12):
        if balance <= 0:
            return balance, interest_paid, paid
        interest = balance * monthly_rate
        principal = monthly_payment - interest + extra
        if principal >= balance:
            interest_paid += interest
            paid += balance + interest
            return 0.0, interest_paid, paid
        balance -= principal
        interest_paid += interest
        paid += monthly_payment + extra
    return balance, interest_paid, paid


def _amortised_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """Standard fixed-rate amortised monthly payment over `term_months`.

    Used to re-derive the payment when a rate step takes effect: the outstanding
    balance is re-amortised over the *remaining* term at the new rate, exactly as
    a lender recalculates on a fixed→follow-on rollover. Straight-line if rate=0.
    """
    if term_months <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / term_months
    r = annual_rate / 12.0
    return principal * r / (1.0 - (1.0 + r) ** -term_months)


_PENSION_WRAPPERS = ("prsa", "occupational_pension")

# State-pension Total Contributions Approach (TCA) constants. From 2025 the
# yearly-average method is being phased out (full TCA by 2034); we model the
# TCA endpoint only — close enough for Budget 2026 base-year projections.
_PRSI_WEEKS_FOR_FULL_PENSION = 2080  # 40 years
_PRSI_WEEKS_MINIMUM = 520            # 10 years required to qualify at all
_HOMECARING_WEEKS_CAP = 1040         # 20 years lifetime cap on HomeCaring credits


def _state_pension_fraction(paid_weeks: int, homecaring_weeks: int) -> float:
    """Fraction of the full state pension a person is entitled to under TCA.

    Returns 0 if below the 520-week qualifying minimum.
    Above the minimum, linearly scales to 1.0 at 2,080 paid+credited weeks.
    HomeCaring credits count toward the scaling cap but NOT toward the 520
    qualifying minimum.
    """
    if paid_weeks < _PRSI_WEEKS_MINIMUM:
        return 0.0
    credited = min(homecaring_weeks, _HOMECARING_WEEKS_CAP)
    total = paid_weeks + credited
    return min(1.0, total / _PRSI_WEEKS_FOR_FULL_PENSION)


@dataclass
class AssetState:
    """Mutable per-asset simulator state. Replaces 6 parallel dicts.

    Synthetic ids: cash bucket = -1, implicit PRSA = -1000-person_id,
    implicit ARF = -2000-person_id. Negative ids never collide with real
    asset rows (Postgres SERIAL is 1-based).
    """
    kind: str
    balance: float
    growth: float
    basis: float
    acquired: int
    owner: int | None
    # Planned-transaction state (Phase 1 property purchase/sale; works for any
    # asset kind). `active` is False for a future purchase that hasn't happened
    # yet — such an asset holds no value, doesn't grow, and is excluded from net
    # worth and the ETF clock until `purchase_year`. `purchase_value`/`deposit`
    # are consumed once on activation. `disposal_year` triggers a planned full
    # sale; `sold` latches so it only fires once.
    active: bool = True
    purchase_year: int | None = None
    purchase_value: float = 0.0
    deposit: float = 0.0
    disposal_year: int | None = None
    sold: bool = False
    # Phase 2 transaction costs / mortgage link.
    linked_liability_id: int | None = None
    stamp_duty_pct: float = 0.0
    selling_cost_pct: float = 0.0
    # Annual product charge (fraction of balance) deducted from growth each year.
    charge_pct: float = 0.0


def _retirement_age_for(person: PersonInput, default: int) -> int:
    return person.retirement_age if person.retirement_age is not None else default


def _is_future_purchase(asset: AssetInput, base_year: int) -> bool:
    """True if the asset is bought after the base year (dormant until then)."""
    return asset.purchase_year is not None and asset.purchase_year > base_year


def _ensure_finite(value: float, field_label: str) -> None:
    """Reject NaN / ±inf at the engine entry-point.

    The API boundary already enforces this via pydantic `allow_inf_nan=False`,
    but the engine is also called from tests, scenario tooling, and (in
    future) batch pipelines that bypass FastAPI. Failing loudly here means a
    bad input surfaces as a clear ValueError instead of silent NaN drift
    through Monte-Carlo bands.
    """
    if not math.isfinite(value):
        raise ValueError(f"{field_label} must be finite, got {value!r}")


def _validate_plan_input(plan: PlanInput) -> None:
    for inc in plan.incomes:
        _ensure_finite(inc.gross_amount, f"income[{inc.id}].gross_amount")
        _ensure_finite(inc.escalation_rate, f"income[{inc.id}].escalation_rate")
    for e in plan.expenses:
        _ensure_finite(e.amount, f"expense[{e.id}].amount")
        _ensure_finite(e.escalation_rate, f"expense[{e.id}].escalation_rate")
    for a in plan.assets:
        _ensure_finite(a.value, f"asset[{a.id}].value")
        _ensure_finite(a.growth_rate, f"asset[{a.id}].growth_rate")
        _ensure_finite(a.cost_basis, f"asset[{a.id}].cost_basis")
        _ensure_finite(a.annual_contribution, f"asset[{a.id}].annual_contribution")
        _ensure_finite(a.deposit, f"asset[{a.id}].deposit")
        _ensure_finite(a.stamp_duty_pct, f"asset[{a.id}].stamp_duty_pct")
        _ensure_finite(a.selling_cost_pct, f"asset[{a.id}].selling_cost_pct")
    for liability in plan.liabilities:
        _ensure_finite(liability.principal, f"liability[{liability.id}].principal")
        _ensure_finite(liability.interest_rate, f"liability[{liability.id}].interest_rate")
        if liability.monthly_payment is not None:
            _ensure_finite(liability.monthly_payment, f"liability[{liability.id}].monthly_payment")
        for adj in liability.adjustments:
            _ensure_finite(adj.value, f"liability[{liability.id}].adjustment[{adj.id}].value")
    for g in plan.goals:
        _ensure_finite(g.target_amount, f"goal[{g.id}].target_amount")
    for c in plan.children:
        _ensure_finite(c.childcare_annual, f"child[{c.id}].childcare_annual")
        _ensure_finite(c.primary_annual, f"child[{c.id}].primary_annual")
        _ensure_finite(c.secondary_annual, f"child[{c.id}].secondary_annual")
        _ensure_finite(
            c.secondary_private_fee_annual, f"child[{c.id}].secondary_private_fee_annual"
        )
        _ensure_finite(c.everyday_annual, f"child[{c.id}].everyday_annual")
    for b in plan.benefits:
        _ensure_finite(b.amount, f"benefit[{b.id}].amount")
        _ensure_finite(b.omv, f"benefit[{b.id}].omv")
        _ensure_finite(b.rate, f"benefit[{b.id}].rate")
        _ensure_finite(b.escalation_rate, f"benefit[{b.id}].escalation_rate")
    a = plan.assumptions
    _ensure_finite(a.inflation_rate, "assumptions.inflation_rate")
    _ensure_finite(a.default_growth_rate, "assumptions.default_growth_rate")
    _ensure_finite(a.property_growth_rate, "assumptions.property_growth_rate")
    _ensure_finite(a.earnings_growth, "assumptions.earnings_growth")
    _ensure_finite(a.state_pension_annual_amount, "assumptions.state_pension_annual_amount")
    _ensure_finite(a.state_pension_escalation_rate, "assumptions.state_pension_escalation_rate")


def simulate(
    plan: PlanInput, *, annual_shocks: list[dict[str, float]] | None = None
) -> list[YearRow]:
    """Run the year-by-year projection.

    `annual_shocks`, when given, is a per-year list (indexed by year offset from
    base_year) of `{asset_kind: additive_growth_delta}` maps applied on top of
    each asset's growth rate that year. This is the hook the Monte Carlo engine
    uses for year-by-year (sequence-of-returns) sampling; None = deterministic.
    """
    _validate_plan_input(plan)
    tax_config = _resolve_tax_config(plan.tax_config)
    years = range(plan.base_year, plan.base_year + plan.projection_years)
    states: dict[int, AssetState] = {
        a.id: AssetState(
            kind=a.kind,
            # A future purchase starts dormant: no balance, no growth, excluded
            # from net worth until its purchase_year.
            balance=0.0 if _is_future_purchase(a, plan.base_year) else a.value,
            growth=a.growth_rate,
            basis=a.cost_basis,
            acquired=a.acquired_year if a.acquired_year is not None else plan.base_year,
            owner=a.owner_person_id,
            active=not _is_future_purchase(a, plan.base_year),
            purchase_year=a.purchase_year,
            purchase_value=a.value,
            deposit=max(0.0, a.deposit),
            disposal_year=a.disposal_year,
            linked_liability_id=a.linked_liability_id,
            stamp_duty_pct=max(0.0, a.stamp_duty_pct),
            selling_cost_pct=max(0.0, a.selling_cost_pct),
            charge_pct=max(0.0, a.annual_charge_pct),
        )
        for a in plan.assets
    }

    liability_balances: dict[int, float] = {
        liability.id: liability.principal
        for liability in plan.liabilities
        if liability.start_year <= plan.base_year
    }
    # Per-liability mutable amortisation state: the rate, contracted payment and
    # recurring overpayment currently in force, plus the effective_year of the
    # last rate step we re-amortised on (so we recompute the payment once per
    # step, not every year — otherwise overpayments would re-lower the payment
    # instead of shortening the term).
    liability_state: dict[int, dict[str, float | None]] = {}
    retired_persons: set[int] = set()  # person ids who have already crystallised
    deceased_persons: set[int] = set()  # person ids who have already died
    # Level annuity income per person, set at retirement when pension_option ==
    # "annuity"; paid (and taxed as PAYE) every year thereafter.
    annuity_income: dict[int, float] = {}
    # One-off taxable pension cash to charge as income in the retirement year
    # (pension_option == "taxable_lump_sum"). Popped once consumed.
    pension_taxable_cash: dict[int, float] = {}
    # PRSI contribution history for the Total Contributions Approach. Seeded
    # from PersonInput.prsi_weeks_at_base_year; accumulates +52 per simulated
    # year that the person earns any PRSI-paying income. HomeCaring weeks
    # accumulate via income-kind "homecaring" (capped at 1,040 = 20 years).
    prsi_weeks: dict[int, int] = {p.id: max(0, p.prsi_weeks_at_base_year) for p in plan.people}
    homecaring_weeks: dict[int, int] = {
        p.id: max(0, min(_HOMECARING_WEEKS_CAP, p.homecaring_weeks_at_base_year))
        for p in plan.people
    }
    # Cumulative lifetime inheritances per (beneficiary_person_id, cat_group) for CAT aggregation.
    lifetime_inheritances: dict[tuple[int, str], float] = {}
    goal_resolved: dict[int, str] = {}  # goal id -> last resolved status (sticks once set)
    rows: list[YearRow] = []

    # "spend" is the canonical one-off-cost goal kind. The legacy kinds were all
    # financially identical one-off spends (consolidated in migration 0024); kept
    # here so an un-migrated row still behaves correctly.
    _COST_BEARING_GOAL_KINDS = {
        "spend", "milestone", "gift", "pre_retirement_spend", "education",
    }

    if len(plan.people) >= 2:
        earners = {
            inc.person_id
            for inc in plan.incomes
            if inc.kind in ("employment", "self_employment")
        }
        any_two_income = len(earners) >= 2
    else:
        any_two_income = False

    def _find_or_create(synthetic_id: int, kind: str, owner: int | None) -> int:
        if synthetic_id not in states:
            states[synthetic_id] = AssetState(
                kind=kind,
                balance=0.0,
                growth=plan.assumptions.default_growth_rate
                if kind != "cash"
                else plan.assumptions.inflation_rate,
                basis=0.0,
                acquired=plan.base_year,
                owner=owner,
            )
        return synthetic_id

    def _person_pension_target(person_id: int) -> int:
        """PRSA preferred, else occupational, else implicit PRSA at id = -1000 - person_id."""
        for aid, st in states.items():
            if st.kind in _PENSION_WRAPPERS and st.owner == person_id:
                return aid
        return _find_or_create(-1000 - person_id, "prsa", person_id)

    def _person_arf_target(person_id: int) -> int:
        for aid, st in states.items():
            if st.kind == "arf" and st.owner == person_id:
                return aid
        return _find_or_create(-2000 - person_id, "arf", person_id)

    def _cash_target() -> int:
        for aid, st in states.items():
            if st.kind == "cash":
                return aid
        return _find_or_create(-1, "cash", None)

    for year in years:
        # ----- 1. Age people -----
        ages = {p.id: _age_in_year(p.dob, year) for p in plan.people}

        notes: list[str] = []

        # ----- 2. Asset growth (start-of-year balances grow over the year) -----
        shock_idx = year - plan.base_year
        year_shocks = (
            annual_shocks[shock_idx]
            if annual_shocks is not None and 0 <= shock_idx < len(annual_shocks)
            else None
        )
        for st in states.values():
            # Dormant future purchases hold no value and don't grow yet.
            if not st.active:
                continue
            # Growth is applied net of the annual product charge (AMC/platform/
            # adviser fee) and any Monte Carlo return shock for this year/kind.
            # Floor the net factor at 0 so charges/shocks can't drive the balance
            # negative even if they exceed growth.
            shock = year_shocks.get(st.kind, 0.0) if year_shocks else 0.0
            st.balance *= max(0.0, 1.0 + st.growth + shock - st.charge_pct)

        # ----- 2a. Planned asset transactions (Phase 1: property purchase/sale).
        # Purchases activate at face value (no growth in the purchase year) and
        # pay their deposit out of cash; the rest of the price is a separately
        # added mortgage. Planned disposals sell the whole position, net of any
        # disposal tax, into cash. Both fire once.
        for aid, st in states.items():
            if not st.active and st.purchase_year == year and not st.sold:
                st.active = True
                st.balance = st.purchase_value
                st.basis = st.purchase_value
                st.acquired = year
                stamp_duty = st.purchase_value * st.stamp_duty_pct
                cash_out = st.deposit + stamp_duty
                if cash_out > 0:
                    states[_cash_target()].balance -= cash_out
                detail = []
                if st.deposit > 0:
                    detail.append(f"EUR {st.deposit:,.0f} deposit")
                if stamp_duty > 0:
                    detail.append(f"EUR {stamp_duty:,.0f} stamp duty")
                notes.append(
                    f"Purchased asset {aid} for EUR {st.purchase_value:,.0f}"
                    + (f" ({', '.join(detail)} from cash)." if detail else ".")
                )
        for aid, st in states.items():
            if st.active and not st.sold and st.disposal_year == year:
                gross = st.balance
                selling_costs = gross * st.selling_cost_pct
                net_sale = gross - selling_costs
                # BTL attracts CGT on the gain (net of selling costs); a primary
                # residence is PPR-exempt; ETF/unwrapped use their disposal rate.
                rate = (
                    tax_config.cgt_rate
                    if st.kind == "property_btl"
                    else _disposal_tax_rate(st.kind, tax_config)
                )
                tax = max(0.0, net_sale - st.basis) * rate
                # Settle the linked mortgage out of the proceeds and stop it.
                payoff = 0.0
                if st.linked_liability_id is not None:
                    payoff = max(0.0, liability_balances.get(st.linked_liability_id, 0.0))
                    if payoff > 0:
                        liability_balances[st.linked_liability_id] = 0.0
                states[_cash_target()].balance += net_sale - tax - payoff
                st.balance = 0.0
                st.basis = 0.0
                st.active = False
                st.sold = True
                bits = [f"Sold asset {aid} for EUR {gross:,.0f}"]
                if selling_costs > 0:
                    bits.append(f"costs EUR {selling_costs:,.0f}")
                bits.append(f"tax EUR {tax:,.0f}" if tax > 0 else "tax-free")
                if payoff > 0:
                    bits.append(f"cleared mortgage EUR {payoff:,.0f}")
                notes.append(", ".join(bits) + ".")

        # ----- 2b. ETF deemed disposal -----
        deemed_tax = 0.0
        for aid, st in states.items():
            if st.kind != "etf_fund":
                continue
            elapsed = year - st.acquired
            if elapsed > 0 and elapsed % tax_config.etf_deemed_disposal_years == 0:
                gain = max(0.0, st.balance - st.basis)
                if gain > 0:
                    tax = gain * tax_config.etf_exit_tax_rate
                    deemed_tax += tax
                    st.basis = st.balance
                    notes.append(
                        f"ETF deemed disposal on asset {aid}: gain EUR {gain:,.0f}, tax EUR {tax:,.0f}."
                    )

        # ----- 2c. Death events — transfer estate, compute CAT -----
        cat_paid_year = 0.0
        life_cover_payout_year = 0.0
        section72_relief_year = 0.0
        estate_transfers_year: dict[int, float] = {}

        for person in plan.people:
            if year < _death_year_for(person) or person.id in deceased_persons:
                continue
            deceased_persons.add(person.id)

            # Collect all assets owned by this person (post-growth values).
            person_asset_ids = [
                aid for aid, st in states.items()
                if st.owner == person.id and st.balance > 0
            ]
            estate_value = sum(states[aid].balance for aid in person_asset_ids)
            estate_transfers_year[person.id] = round(estate_value, 2)

            # Remove assets from the deceased — they will be re-allocated below.
            for aid in person_asset_ids:
                states[aid].balance = 0.0

            # Apply bequests.
            person_bequests = [b for b in plan.bequests if b.from_person_id == person.id]
            person_cat = 0.0
            for bequest in person_bequests:
                share = bequest.share_pct * estate_value
                if share <= 0:
                    continue
                if bequest.to_person_id is None:
                    # External beneficiary — value leaves the plan.
                    notes.append(
                        f"{person.name}'s estate: EUR {share:,.0f} ({bequest.share_pct:.0%}) "
                        "to external beneficiary."
                    )
                    continue
                # Internal — compute CAT, route net to plan cash.
                key = (bequest.to_person_id, bequest.cat_group)
                prior = lifetime_inheritances.get(key, 0.0)
                cat = cat_ie.compute_cat(share, bequest.cat_group, prior, tax_config)
                lifetime_inheritances[key] = prior + share
                person_cat += cat
                net = share - cat
                states[_cash_target()].balance += net

            # Section 72 relief: an in-force Revenue-approved policy on the
            # deceased pays the inheritance CAT tax-free. Relief caps at the CAT
            # due; any surplus still passes to survivors. The full payout reaches
            # cash — the covered CAT is effectively refunded to beneficiaries
            # (the policy, not they, paid Revenue) and any excess is theirs —
            # while the reported CAT drops by the relief.
            s72_payout = sum(
                max(0.0, pol.sum_assured)
                for pol in plan.life_policies
                if pol.person_id == person.id and pol.kind == "section_72"
                and pol.start_year <= year and (pol.end_year is None or year <= pol.end_year)
            )
            if s72_payout > 0:
                cat_after, _excess = cat_ie.apply_section72(person_cat, s72_payout)
                relief = person_cat - cat_after
                states[_cash_target()].balance += s72_payout
                section72_relief_year += relief
                notes.append(
                    f"{person.name}'s Section 72 policy pays EUR {s72_payout:,.0f}, "
                    f"covering EUR {relief:,.0f} of CAT."
                )
                person_cat = cat_after

            cat_paid_year += person_cat
            notes.append(
                f"{person.name} passes: estate EUR {estate_value:,.0f}"
                + (f", CAT EUR {person_cat:,.0f}." if person_cat > 0 else ".")
            )

            # Term-life payout: any in-force policy on the deceased pays its sum
            # assured tax-free straight to survivors' cash. Life-cover proceeds
            # to a named beneficiary bypass the estate, so this is separate from
            # (and untaxed by) the CAT computation above.
            for pol in plan.life_policies:
                if pol.person_id != person.id or pol.kind != "term_life":
                    continue
                in_force = pol.start_year <= year and (pol.end_year is None or year <= pol.end_year)
                payout = max(0.0, pol.sum_assured)
                if in_force and payout > 0:
                    states[_cash_target()].balance += payout
                    life_cover_payout_year += payout
                    notes.append(
                        f"{person.name}'s life cover '{pol.name}' pays "
                        f"EUR {payout:,.0f} to survivors."
                    )

        # ----- 3. Per-person income / pension lifecycle -----
        person_rows: list[PersonYear] = []
        income_by_kind: dict[str, float] = {}
        # Gross earned income per person BEFORE pension deduction — used by % of gross mode.
        gross_earned_by_person: dict[int, float] = {}

        pension_contributions_total = 0.0
        employer_pension_contributions_total = 0.0
        pension_lump_sum_total = 0.0
        pension_lump_sum_tax_total = 0.0
        arf_drawdowns_total = 0.0
        state_pension_total = 0.0
        db_pension_total = 0.0
        benefits_in_kind_total = 0.0

        for person in plan.people:
            age = ages[person.id]
            # Skip persons who have died (this year's death is handled in step 2c above).
            if year >= _death_year_for(person):
                continue
            retire_age = _retirement_age_for(person, plan.assumptions.state_pension_age)
            is_retired_now = age >= retire_age

            # 3a. Earned income from IncomeSource records.
            earned_for_it = 0.0
            earned_for_usc = 0.0
            earned_for_prsi = 0.0
            has_paye_income = False
            has_self_employment = False
            has_homecaring_marker = False
            requested_pension_pct = 0.0
            employer_contribution_per_source: list[tuple[float, float]] = []
            for inc in plan.incomes:
                if inc.person_id != person.id or not _income_active(inc, year):
                    continue
                # HomeCaring is a zero-gross marker — only used to credit weeks
                # toward the state pension under TCA. Skip all monetary effects.
                if inc.kind == "homecaring":
                    has_homecaring_marker = True
                    continue
                # Earned income stops at retirement even if end_year is open.
                # Passive kinds (rental, annuity, other) keep flowing; state
                # pension and ARF drawdowns are auto-injected elsewhere. A bonus
                # is employment-related, so it stops too even when modelled with a
                # passive kind (the one-click bonus uses kind="other").
                if is_retired_now and (
                    inc.kind in ("employment", "self_employment") or inc.is_bonus
                ):
                    continue
                amt = _escalate(inc.gross_amount, inc.escalation_rate, year - inc.start_year)
                # Rental income is taxed on profit, not gross: deduct allowable
                # expenses (a % of gross) and the wear-and-tear capital allowance
                # on furnishings (straight-line over the config's window). The
                # profit figure flows to IT/USC/PRSI and to income_by_kind.
                if inc.kind == "rental":
                    expenses = amt * min(1.0, max(0.0, inc.rental_expenses_pct))
                    years_let = year - inc.start_year
                    wear_and_tear = (
                        max(0.0, inc.furnishings_value) * tax_config.rental_wear_tear_rate
                        if 0 <= years_let < tax_config.rental_wear_tear_years
                        else 0.0
                    )
                    amt = max(0.0, amt - expenses - wear_and_tear)
                earned_for_it += amt
                if inc.pays_usc:
                    earned_for_usc += amt
                if inc.pays_prsi and not is_retired_now:
                    earned_for_prsi += amt
                if inc.kind == "self_employment":
                    has_self_employment = True
                elif _is_paye_kind(inc.kind):
                    has_paye_income = True
                if inc.pension_contribution_pct > requested_pension_pct:
                    requested_pension_pct = inc.pension_contribution_pct
                if inc.employer_pension_contribution_pct > 0:
                    employer_contribution_per_source.append(
                        (amt, inc.employer_pension_contribution_pct)
                    )
                income_by_kind[inc.kind] = income_by_kind.get(inc.kind, 0.0) + amt

            gross_earned_by_person[person.id] = earned_for_it

            # 3a-ii. PRSI / HomeCaring week accumulation for the state pension
            # TCA fraction. Pre-retirement only; post-retirement is locked.
            if not is_retired_now:
                if earned_for_prsi > 0:
                    prsi_weeks[person.id] += 52
                if has_homecaring_marker:
                    homecaring_weeks[person.id] = min(
                        _HOMECARING_WEEKS_CAP, homecaring_weeks[person.id] + 52
                    )

            # 3b. Pension contribution (pre-retirement, IT-deductible employee + employer top-up).
            pension_contribution = 0.0
            if not is_retired_now and requested_pension_pct > 0 and earned_for_it > 0:
                pension_contribution = pension_ie.relievable_contribution(
                    earned_for_it, requested_pension_pct, age, tax_config
                )
                if pension_contribution > 0:
                    states[_person_pension_target(person.id)].balance += pension_contribution
                    pension_contributions_total += pension_contribution

            # 3b-ii. AVC (Additional Voluntary Contributions) — pre-tax, jointly capped.
            # Each pension asset owned by this person may carry an AVC setting.
            # The combined (regular + AVC) amount cannot exceed the age-based cap.
            if not is_retired_now and earned_for_it > 0:
                cap_pct = pension_ie.age_contribution_cap_pct(age, tax_config)
                cap_income = min(earned_for_it, tax_config.pension_earnings_cap)
                cap_amount = cap_pct * cap_income
                remaining_cap = max(0.0, cap_amount - pension_contribution)

                for asset in plan.assets:
                    if asset.kind not in _PENSION_WRAPPERS:
                        continue
                    if asset.owner_person_id != person.id:
                        continue
                    if remaining_cap <= 0:
                        break
                    if asset.avc_annual > 0:
                        raw_avc = asset.avc_annual
                    elif asset.avc_pct_of_gross > 0:
                        raw_avc = max(0.0, earned_for_it * asset.avc_pct_of_gross)
                    else:
                        continue
                    effective_avc = min(raw_avc, remaining_cap)
                    remaining_cap -= effective_avc
                    states[asset.id].balance += effective_avc
                    states[asset.id].basis += effective_avc
                    pension_contribution += effective_avc
                    pension_contributions_total += effective_avc

            # 3b-ii. Employer pension contribution: lands in the wrapper, does NOT
            # reduce the employee's taxable income or the household cash flow (employer-funded).
            # No age cap (employer contributions sit outside the employee's relievable cap).
            if not is_retired_now and employer_contribution_per_source:
                employer_total = sum(amt * pct for amt, pct in employer_contribution_per_source)
                if employer_total > 0:
                    states[_person_pension_target(person.id)].balance += employer_total
                    employer_pension_contributions_total += employer_total

            # 3c. Retirement crystallisation (one-shot in the trigger year).
            crystallised_lump_sum = 0.0
            crystallised_lump_sum_tax = 0.0
            if is_retired_now and person.id not in retired_persons:
                pot = sum(
                    st.balance
                    for st in states.values()
                    if st.kind in _PENSION_WRAPPERS and st.owner == person.id and st.balance > 0
                )
                if pot > 0:
                    lump_sum_pct = max(0.0, min(0.25, person.lump_sum_pct))
                    lump_sum = lump_sum_pct * pot
                    remainder = pot - lump_sum
                    crystallised_lump_sum = lump_sum
                    crystallised_lump_sum_tax = pension_ie.lump_sum_tax(lump_sum, tax_config)
                    net_lump_sum = lump_sum - crystallised_lump_sum_tax

                    # Zero out pension wrappers owned by this person.
                    for st in states.values():
                        if st.kind in _PENSION_WRAPPERS and st.owner == person.id:
                            st.balance = 0.0

                    states[_cash_target()].balance += net_lump_sum

                    # Disposition of the post-lump-sum remainder depends on the
                    # person's chosen pension option.
                    option = person.pension_option
                    if option == "annuity":
                        rate = max(0.0, person.annuity_rate)
                        annuity_income[person.id] = remainder * rate
                        notes.append(
                            f"{person.name} retires: pot EUR {pot:,.0f} → lump sum EUR {lump_sum:,.0f} "
                            f"(tax EUR {crystallised_lump_sum_tax:,.0f}) + annuity EUR "
                            f"{remainder * rate:,.0f}/yr from EUR {remainder:,.0f}."
                        )
                    elif option == "taxable_lump_sum":
                        # Whole remainder taken as cash this year, taxed as income.
                        pension_taxable_cash[person.id] = remainder
                        notes.append(
                            f"{person.name} retires: pot EUR {pot:,.0f} → lump sum EUR {lump_sum:,.0f} "
                            f"(tax EUR {crystallised_lump_sum_tax:,.0f}) + EUR {remainder:,.0f} taken "
                            f"as taxable cash."
                        )
                    else:  # "arf" (default)
                        states[_person_arf_target(person.id)].balance += remainder
                        notes.append(
                            f"{person.name} retires: pot EUR {pot:,.0f} → lump sum EUR {lump_sum:,.0f} "
                            f"(tax EUR {crystallised_lump_sum_tax:,.0f}) + ARF EUR {remainder:,.0f}."
                        )
                retired_persons.add(person.id)

            pension_lump_sum_total += crystallised_lump_sum
            pension_lump_sum_tax_total += crystallised_lump_sum_tax

            # ARF drawdown is computed at step 3d below, AFTER the other
            # retirement income (state pension / DB / annuity) is known — the
            # band-fill strategy needs the year's non-ARF taxable income to size
            # the drawdown against the standard-rate band.
            arf_drawdown = 0.0

            # 3e. State pension auto-injection, scaled by TCA entitlement.
            state_pension_amt = 0.0
            if age >= plan.assumptions.state_pension_age:
                # Escalate by the dedicated state pension rate (historically ~1.5–2%,
                # much lower than general inflation due to frequent multi-year freezes).
                full_amt = _escalate(
                    plan.assumptions.state_pension_annual_amount,
                    plan.assumptions.state_pension_escalation_rate,
                    year - plan.base_year,
                )
                fraction = _state_pension_fraction(
                    prsi_weeks[person.id], homecaring_weeks[person.id]
                )
                state_pension_amt = full_amt * fraction
                if state_pension_amt > 0:
                    state_pension_total += state_pension_amt
                    income_by_kind["state_pension"] = (
                        income_by_kind.get("state_pension", 0.0) + state_pension_amt
                    )

            # 3e-i. Defined-benefit / final-salary pension income. Guaranteed
            # annual income from the scheme's normal retirement age, computed as
            # accrual_rate × service_years × final_salary and indexed by
            # revaluation_rate (deferment + in payment). PAYE-taxed, PRSI-exempt.
            # An optional tax-free lump sum lands in cash in the retirement year.
            db_pension_amt = 0.0
            for dp in plan.db_pensions:
                if dp.person_id != person.id:
                    continue
                start_year = person.dob.year + dp.normal_retirement_age
                if year < start_year:
                    continue
                base = dp.accrual_rate * dp.service_years * dp.final_salary
                db_pension_amt += base * (1.0 + dp.revaluation_rate) ** max(0, year - plan.base_year)
                if year == start_year and dp.tax_free_lump_sum > 0:
                    states[_cash_target()].balance += dp.tax_free_lump_sum
                    notes.append(
                        f"{person.name}'s DB pension '{dp.name}' starts: tax-free lump sum "
                        f"EUR {dp.tax_free_lump_sum:,.0f}."
                    )
            if db_pension_amt > 0:
                db_pension_total += db_pension_amt
                income_by_kind["db_pension"] = (
                    income_by_kind.get("db_pension", 0.0) + db_pension_amt
                )

            # 3e-ii. Annuity income (paid every year once an annuity is bought) and
            # one-off taxable cash drawdown (taxable_lump_sum option, retirement year).
            # Both are PAYE-taxed pension income, PRSI-exempt like ARF/state pension.
            annuity_amt = annuity_income.get(person.id, 0.0)
            if annuity_amt > 0:
                income_by_kind["annuity"] = income_by_kind.get("annuity", 0.0) + annuity_amt
            taxable_cash = pension_taxable_cash.pop(person.id, 0.0)
            if taxable_cash > 0:
                income_by_kind["pension_taxable_cash"] = (
                    income_by_kind.get("pension_taxable_cash", 0.0) + taxable_cash
                )

            # 3d. ARF drawdown (post-retirement): the statutory minimum, an
            # optional voluntary target %, or — with band-fill — drawn up to the
            # top of the standard-rate band given the year's other income, to use
            # cheap 20% headroom before it's lost. Placed after the other
            # retirement income above so band-fill can size that headroom.
            if is_retired_now:
                arf_total = sum(
                    st.balance
                    for st in states.values()
                    if st.kind == "arf" and st.owner == person.id
                )
                if arf_total > 0:
                    min_pct = pension_ie.arf_minimum_drawdown_pct(age, arf_total, tax_config)
                    target_pct = person.arf_target_drawdown_pct or 0.0
                    # Clamp to 1.0 so we can't withdraw more than the pot.
                    pct = min(1.0, max(min_pct, target_pct))
                    arf_drawdown = arf_total * pct
                    if person.arf_band_fill:
                        band_status = _filing_status_for_person(
                            person, plan.people, any_two_income, plan.filing_status,
                            age=age,
                            is_paye_employee=(
                                has_paye_income or not has_self_employment or is_retired_now
                            ),
                            year=year, marriage_year=plan.marriage_year,
                        )
                        srco, _lbl = tax_ie.standard_rate_band(band_status, tax_config)
                        non_arf_taxable = (
                            max(0.0, earned_for_it) + state_pension_amt + db_pension_amt
                            + annuity_amt + taxable_cash
                        )
                        headroom = max(0.0, srco - non_arf_taxable)
                        # Fill the band, but never below the statutory minimum and
                        # never more than the pot.
                        arf_drawdown = min(arf_total, max(arf_drawdown, headroom))
                    if arf_drawdown > 0:
                        # Pull pro-rata from each ARF owned by this person.
                        for st in states.values():
                            if st.kind != "arf" or st.owner != person.id:
                                continue
                            share = st.balance / arf_total
                            st.balance -= arf_drawdown * share
                        arf_drawdowns_total += arf_drawdown
                        income_by_kind["arf_drawdown"] = (
                            income_by_kind.get("arf_drawdown", 0.0) + arf_drawdown
                        )

            # 3e-iii. Employer benefits-in-kind (notional pay). The cash
            # equivalent of each active benefit is charged to IT/USC/PRSI but
            # never received as cash and never paid by the household, so it
            # raises tax without touching the cash flow. Medical-insurance BIK
            # also entitles the employee to the 20% (capped) relief credit,
            # because tax relief at source is not granted when the employer
            # pays. BIK is employment-related, so it stops at retirement.
            person_bik_total = 0.0
            person_medical_relief = 0.0
            if not is_retired_now:
                for b in plan.benefits:
                    if b.person_id != person.id or not _benefit_active(b, year):
                        continue
                    escalated = _escalate(b.amount, b.escalation_rate, year - b.start_year)
                    ce = bik_ie.cash_equivalent(
                        kind=b.kind,
                        amount=escalated,
                        omv=b.omv,
                        rate=b.rate,
                        loan_is_qualifying=b.loan_is_qualifying,
                        tax_config=tax_config,
                    )
                    if ce <= 0:
                        continue
                    person_bik_total += ce
                    if b.kind == "medical_insurance":
                        person_medical_relief += bik_ie.medical_insurance_relief(
                            ce, b.relief_adults, b.relief_children, tax_config
                        )
            benefits_in_kind_total += person_bik_total

            # 3f. Tax computation.
            pension_income = (
                arf_drawdown + state_pension_amt + annuity_amt + taxable_cash + db_pension_amt
            )
            taxable_for_it = (
                max(0.0, earned_for_it - pension_contribution) + pension_income + person_bik_total
            )
            taxable_for_usc = max(0.0, earned_for_usc) + pension_income + person_bik_total
            # BIK is PRSI-able; ARF / annuity / state pension stay exempt.
            taxable_for_prsi = earned_for_prsi + person_bik_total

            status = _filing_status_for_person(
                person,
                plan.people,
                any_two_income,
                plan.filing_status,
                age=age,
                is_paye_employee=has_paye_income or not has_self_employment or is_retired_now,
                year=year,
                marriage_year=plan.marriage_year,
            )
            if person_medical_relief > 0:
                status = replace(status, medical_insurance_relief=person_medical_relief)

            it, _band = tax_ie.income_tax(taxable_for_it, status, tax_config)
            u = tax_ie.usc(taxable_for_usc, tax_config)
            p_prsi = tax_ie.prsi(
                taxable_for_prsi,
                is_paye=status.is_paye_employee,
                tax_config=tax_config,
            )
            total = it + u + p_prsi

            # Report TRUE gross (before the pension contribution, which only
            # reduces the IT-taxable base, not actual earnings). net_income here
            # is gross − tax, i.e. take-home BEFORE the pension contribution is
            # diverted; the contribution is subtracted once later in the cash
            # flow (it lands in the pension pot, not in spendable cash). Using
            # taxable_for_it as "gross" previously double-removed the pension —
            # once here and again in the cash flow.
            #
            # BIK inflated taxable_for_it for the tax computation, but it is
            # notional pay (never received as cash). Strip it back out of the
            # reported gross so net_income only loses the *tax* on the benefit,
            # not the benefit value itself — the employer funds the benefit, so
            # it never enters or leaves household cash.
            true_gross = (taxable_for_it - person_bik_total) + pension_contribution
            person_rows.append(
                PersonYear(
                    person_id=person.id,
                    name=person.name,
                    age=age,
                    gross_income=round(true_gross, 2),
                    income_tax=round(it, 2),
                    usc=round(u, 2),
                    prsi=round(p_prsi, 2),
                    net_income=round(true_gross - total, 2),
                )
            )

        gross_income_total = sum(pr.gross_income for pr in person_rows)
        total_it = sum(pr.income_tax for pr in person_rows)
        total_usc = sum(pr.usc for pr in person_rows)
        total_prsi = sum(pr.prsi for pr in person_rows)
        total_tax = total_it + total_usc + total_prsi
        net_income = gross_income_total - total_tax

        # ----- 3.4. Child Benefit (tax-free, paid to the primary carer) -----
        # €140/mo × 12 per child under the age limit, escalated. Adds to
        # household gross + net income; no IT / USC / PRSI charge.
        child_benefit_total = 0.0
        for child in plan.children:
            if not child.active:
                continue
            child_age = year - child.dob.year
            if 0 <= child_age < tax_config.child_benefit_age_limit:
                annual = _escalate(
                    tax_config.child_benefit_monthly * 12.0,
                    tax_config.child_benefit_escalation,
                    year - plan.base_year,
                )
                child_benefit_total += annual
        if child_benefit_total > 0:
            gross_income_total += child_benefit_total
            net_income += child_benefit_total
            income_by_kind["child_benefit"] = (
                income_by_kind.get("child_benefit", 0.0) + child_benefit_total
            )

        # ----- 3.5. Asset contributions (fixed / % net income / % gross income) -----
        # Funded from cash flow (deducted in step 5); cost basis rises by the amount contributed.
        # Net-income mode uses post-tax income; gross-income mode uses earnings before pension
        # deduction (the truest "gross" available per person).
        asset_contributions_total = 0.0
        net_income_by_person: dict[int, float] = {pr.person_id: pr.net_income for pr in person_rows}
        gross_total = sum(gross_earned_by_person.values())
        for asset in plan.assets:
            start = asset.contribution_start_year if asset.contribution_start_year is not None else plan.base_year
            end = asset.contribution_end_year
            if year < start or (end is not None and year > end):
                continue
            if asset.annual_contribution > 0:
                contrib = asset.annual_contribution
            elif asset.contribution_pct_of_net_income > 0:
                base = (
                    net_income_by_person.get(asset.owner_person_id, 0.0)
                    if asset.owner_person_id is not None
                    else net_income
                )
                contrib = max(0.0, base * asset.contribution_pct_of_net_income)
            elif asset.contribution_pct_of_gross_income > 0:
                base = (
                    gross_earned_by_person.get(asset.owner_person_id, 0.0)
                    if asset.owner_person_id is not None
                    else gross_total
                )
                contrib = max(0.0, base * asset.contribution_pct_of_gross_income)
            else:
                continue
            states[asset.id].balance += contrib
            states[asset.id].basis += contrib
            asset_contributions_total += contrib

        # ----- 4. Expenses -----
        expenses_by_category: dict[str, float] = {}
        for e in plan.expenses:
            if not _expense_active(e, year):
                continue
            amt = _escalate(e.amount, e.escalation_rate, year - e.start_year)
            expenses_by_category[e.category] = expenses_by_category.get(e.category, 0.0) + amt

        # ----- 4a-i. Per-child rearing costs, age-gated by education stage -----
        # Each cost band applies only while the child's age sits in its window
        # (boundaries from TaxConfig). Secondary private fees stack on the public
        # secondary cost. Everyday (food/clothes) runs the whole dependency span
        # and is opt-in (defaults 0) to avoid double-counting household expenses.
        # All escalate by inflation. Inactive (scenario-disabled) children skip.
        child_costs_total = 0.0
        for child in plan.children:
            if not child.active:
                continue
            child_age = year - child.dob.year
            if child_age < 0:
                continue
            raw = 0.0
            if child_age < tax_config.child_primary_start_age:
                raw += child.childcare_annual
            elif child_age < tax_config.child_secondary_start_age:
                raw += child.primary_annual
            elif child_age < tax_config.child_secondary_end_age:
                raw += child.secondary_annual
                if child.secondary_is_private:
                    raw += child.secondary_private_fee_annual
            if child_age < tax_config.child_secondary_end_age:
                raw += child.everyday_annual
            if raw > 0:
                child_costs_total += _escalate(
                    raw, plan.assumptions.inflation_rate, year - plan.base_year
                )
        if child_costs_total > 0:
            expenses_by_category["children"] = (
                expenses_by_category.get("children", 0.0) + child_costs_total
            )

        # ----- 4a-ii. Protection premiums (term life) -----
        # Paid while the policy is in force and the insured is still alive.
        # A real cash outgoing, so it sits in expenses like any other cost.
        protection_premiums_total = 0.0
        for pol in plan.life_policies:
            in_force = pol.start_year <= year and (pol.end_year is None or year <= pol.end_year)
            insured = next((p for p in plan.people if p.id == pol.person_id), None)
            alive = insured is not None and year < _death_year_for(insured)
            if in_force and alive and pol.premium_annual > 0:
                protection_premiums_total += pol.premium_annual
        if protection_premiums_total > 0:
            expenses_by_category["protection"] = (
                expenses_by_category.get("protection", 0.0) + protection_premiums_total
            )

        # ----- 4a. Cost-bearing goals due this year -----
        goals_due: list[GoalInput] = [
            g for g in plan.goals
            if g.kind in _COST_BEARING_GOAL_KINDS and g.target_year == year
        ]
        if goals_due:
            goals_total = sum(g.target_amount for g in goals_due)
            expenses_by_category["goals"] = (
                expenses_by_category.get("goals", 0.0) + goals_total
            )

        # ----- 4b. Liability amortisation -----
        debt_service = 0.0
        for liability in plan.liabilities:
            if year < liability.start_year:
                continue
            if liability.id not in liability_balances:
                liability_balances[liability.id] = liability.principal
            st = liability_state.get(liability.id)
            if st is None:
                st = {
                    "rate": liability.interest_rate,
                    "payment": liability.monthly_payment,
                    "overpay": liability.monthly_overpayment,
                    "last_rate_year": None,
                }
                liability_state[liability.id] = st
            bal = liability_balances[liability.id]
            # One-off lump-sum capital repayments effective this exact year.
            for adj in liability.adjustments:
                if adj.kind == "lump_sum" and adj.effective_year == year:
                    bal = max(0.0, bal - max(0.0, adj.value))
            if bal <= 0:
                liability_balances[liability.id] = 0.0
                continue
            # Rate step: when a new rate first takes effect, re-amortise the
            # outstanding balance over the remaining term at the new rate and
            # hold that payment (lender-style fixed→follow-on recalculation).
            rate_adjs = [
                a for a in liability.adjustments
                if a.kind == "rate" and a.effective_year <= year
            ]
            if rate_adjs:
                latest = max(rate_adjs, key=lambda a: a.effective_year)
                if st["last_rate_year"] != latest.effective_year:
                    months_elapsed = 12 * (year - liability.start_year)
                    remaining = max(1, liability.term_months - months_elapsed)
                    st["rate"] = latest.value
                    st["payment"] = _amortised_payment(bal, latest.value, remaining)
                    st["last_rate_year"] = latest.effective_year
            # Overpayment step: latest effective change overrides the base value.
            op_adjs = [
                a for a in liability.adjustments
                if a.kind == "overpayment" and a.effective_year <= year
            ]
            if op_adjs:
                st["overpay"] = max(op_adjs, key=lambda a: a.effective_year).value
            monthly_rate = st["rate"] / 12.0
            new_bal, _interest_paid, paid = _amortise_year(
                bal, monthly_rate, st["payment"], st["overpay"]
            )
            liability_balances[liability.id] = new_bal
            debt_service += paid
        if debt_service > 0:
            expenses_by_category["debt_service"] = (
                expenses_by_category.get("debt_service", 0.0) + debt_service
            )

        expenses_total = sum(expenses_by_category.values())

        # ----- 5. Cash flow -----
        # net_income is take-home (true gross − tax) BEFORE the pension
        # contribution is diverted, so the contribution is subtracted exactly
        # once here — it leaves spendable cash for the pension pot. Lump sum tax
        # is a separate one-shot bill.
        cash_flow = (
            net_income
            - expenses_total
            - deemed_tax
            - pension_lump_sum_tax_total
            - pension_contributions_total
            - asset_contributions_total
        )
        investment_tax = deemed_tax + pension_lump_sum_tax_total
        realised_gains = 0.0

        # ----- 6. Apply surplus / shortfall -----
        withdrawals: dict[int, float] = {}
        had_shortfall = False
        if cash_flow >= 0:
            had_real_cash = any(st.kind == "cash" for st in states.values())
            states[_cash_target()].balance += cash_flow
            if not had_real_cash and year == plan.base_year:
                notes.append("No cash asset — surplus accumulating in implicit cash bucket.")
        else:
            need = -cash_flow
            unwrapped_gain = 0.0
            for kind in LIQUIDATION_ORDER:
                if need <= 0:
                    break
                rate = _disposal_tax_rate(kind, tax_config)
                for aid, st in list(states.items()):
                    if st.kind != kind or st.balance <= 0:
                        continue
                    gross, new_bal, new_basis, tax = _withdraw_with_tax(
                        st.balance, st.basis, need, rate
                    )
                    if gross <= 0:
                        continue
                    st.balance = new_bal
                    st.basis = new_basis
                    withdrawals[aid] = withdrawals.get(aid, 0.0) + gross
                    investment_tax += tax
                    gain_realised = (tax / rate) if rate > 0 else 0.0
                    realised_gains += gain_realised
                    if kind == "investment_unwrapped":
                        unwrapped_gain += gain_realised
                    need -= (gross - tax)
                    if need <= 0:
                        break

            # CGT annual exemption: first €1,270 of unwrapped gains is tax-free.
            if unwrapped_gain > 0:
                exempt_gain = min(unwrapped_gain, tax_config.cgt_annual_exemption)
                refund = exempt_gain * tax_config.cgt_rate
                investment_tax = max(0.0, investment_tax - refund)

            if need > 0:
                had_shortfall = True
                notes.append(f"Shortfall of EUR {need:,.0f} could not be funded — assets exhausted.")

        # Snapshot
        balances_snapshot = {
            aid: round(st.balance, 2) for aid, st in states.items() if st.balance > 0.005 or aid >= 0
        }
        balances_by_kind: dict[str, float] = {}
        for aid, bal in balances_snapshot.items():
            k = states[aid].kind if aid in states else "unknown"
            balances_by_kind[k] = balances_by_kind.get(k, 0.0) + bal

        liability_snapshot = {
            lid: round(bal, 2) for lid, bal in liability_balances.items() if bal > 0.005
        }
        debt_outstanding = sum(liability_snapshot.values())
        net_worth = sum(balances_snapshot.values()) - debt_outstanding

        # Accessible net worth: subtract pension wrappers owned by anyone still
        # pre-retirement this year. PRSA/occupational/AVC are inaccessible until
        # the owner hits retirement_age (or 50/55 minimums in real Irish rules,
        # but we follow the per-person retirement_age the user set). ARFs only
        # exist post-retirement so always counted. Property is liquid via the
        # liquidation order so kept in.
        locked = 0.0
        for aid, bal in balances_snapshot.items():
            st = states[aid]
            if st.kind not in ("prsa", "occupational_pension", "avc"):
                continue
            if st.owner is None:
                continue
            owner_age = ages.get(st.owner)
            owner = next((p for p in plan.people if p.id == st.owner), None)
            if owner_age is None or owner is None:
                continue
            retire_age = _retirement_age_for(owner, plan.assumptions.state_pension_age)
            if owner_age < retire_age:
                locked += bal
        accessible_net_worth = net_worth - locked

        # Gross liquid-asset value: cash / deposits / unwrapped investments /
        # ETFs only, never netted against debt. Property and pensions/ARFs are
        # excluded. Gates goal affordability/achievability below.
        liquid_assets = sum(
            bal
            for aid, bal in balances_snapshot.items()
            if states[aid].kind in LIQUID_ASSET_KINDS
        )

        # ----- 7. Goal status for this year -----
        goal_status: dict[int, str] = {}
        for g in plan.goals:
            if year < g.target_year:
                goal_status[g.id] = goal_resolved.get(g.id, "pending")
                continue
            if year > g.target_year:
                goal_status[g.id] = goal_resolved.get(g.id, "pending")
                continue
            # year == target_year — resolve now.
            # Net-worth goals: status reflects whether the threshold is met at the snapshot
            # year — distinct from cost-bearing goals (which actually completed an event).
            if g.kind == "retirement":
                status = "achieved"
            elif g.kind == "net_worth":
                # Grade against liquid assets only (cash / deposits / unwrapped
                # investments / ETFs). Property and pensions don't count — a
                # target is only "met" if it's reachable from liquid wealth
                # without selling the house or raiding a pension.
                status = "met" if liquid_assets >= g.target_amount else "below_target"
            elif g.kind in _COST_BEARING_GOAL_KINDS:
                status = "missed" if had_shortfall else "achieved"
            else:
                status = "achieved"
            goal_status[g.id] = status
            goal_resolved[g.id] = status

        rows.append(
            YearRow(
                year=year,
                ages=ages,
                persons=person_rows,
                gross_income_total=round(gross_income_total, 2),
                income_by_kind={k: round(v, 2) for k, v in income_by_kind.items()},
                total_tax=round(total_tax, 2),
                income_tax=round(total_it, 2),
                usc=round(total_usc, 2),
                prsi=round(total_prsi, 2),
                net_income_total=round(net_income, 2),
                expenses_total=round(expenses_total, 2),
                expenses_by_category={k: round(v, 2) for k, v in expenses_by_category.items()},
                surplus_or_shortfall=round(cash_flow, 2),
                asset_balances=balances_snapshot,
                asset_balances_by_kind={k: round(v, 2) for k, v in balances_by_kind.items()},
                withdrawals_by_asset={k: round(v, 2) for k, v in withdrawals.items()},
                net_worth=round(net_worth, 2),
                accessible_net_worth=round(accessible_net_worth, 2),
                liquid_assets=round(liquid_assets, 2),
                liability_balances=liability_snapshot,
                debt_outstanding=round(debt_outstanding, 2),
                investment_tax=round(investment_tax, 2),
                realised_gains=round(realised_gains, 2),
                pension_contributions=round(pension_contributions_total, 2),
                employer_pension_contributions=round(employer_pension_contributions_total, 2),
                pension_lump_sum=round(pension_lump_sum_total, 2),
                pension_lump_sum_tax=round(pension_lump_sum_tax_total, 2),
                arf_drawdowns=round(arf_drawdowns_total, 2),
                state_pension_total=round(state_pension_total, 2),
                db_pension_total=round(db_pension_total, 2),
                goal_status=goal_status,
                notes=notes,
                cat_paid=round(cat_paid_year, 2),
                estate_transfers=estate_transfers_year,
                asset_contributions=round(asset_contributions_total, 2),
                had_shortfall=had_shortfall,
                benefits_in_kind_total=round(benefits_in_kind_total, 2),
                protection_premiums_total=round(protection_premiums_total, 2),
                life_cover_payout=round(life_cover_payout_year, 2),
                cover_gap=round(max(0.0, debt_outstanding - liquid_assets), 2),
                section72_cat_relief=round(section72_relief_year, 2),
            )
        )

    return rows
