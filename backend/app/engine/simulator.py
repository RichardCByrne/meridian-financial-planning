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
from dataclasses import dataclass, field
from datetime import date

from app.engine import cat_ie, pension_ie, tax_ie
from app.engine.liquidation import (
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


@dataclass
class BequestInput:
    id: int
    from_person_id: int
    to_person_id: int | None  # None = external beneficiary (leaves plan)
    cat_group: str  # "A", "B", "C", "exempt"
    share_pct: float  # fraction of estate (0.0–1.0)


@dataclass
class GoalInput:
    id: int
    kind: str
    name: str
    target_amount: float
    target_year: int
    linked_person_id: int | None = None


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
    # Tax-rule constants. None = use IRELAND_2026_OFFICIAL.
    tax_config: TaxConfig | None = None
    # Filing status override. None → auto (1 person → single, 2+ → married).
    # Explicit "cohabiting" forces single-band tax for both people, which is
    # how Irish Revenue actually treats unmarried couples.
    filing_status: str | None = None


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
    goal_status: dict[int, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    cat_paid: float = 0.0
    estate_transfers: dict[int, float] = field(default_factory=dict)
    asset_contributions: float = 0.0
    had_shortfall: bool = False
    # Net worth minus assets locked to a person's pre-retirement pension wrappers
    # (prsa / occupational_pension / avc). ARF balances are always accessible since
    # they only exist post-retirement and are drawn down automatically. Property,
    # cash, investments stay accessible regardless of age.
    accessible_net_worth: float = 0.0


def _age_in_year(dob: date, year: int) -> int:
    return year - dob.year


def _income_active(inc: IncomeInput, year: int) -> bool:
    if year < inc.start_year:
        return False
    if inc.end_year is not None and year > inc.end_year:
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
) -> FilingStatus:
    if plan_filing_status == "married":
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
    balance: float, monthly_rate: float, monthly_payment: float
) -> tuple[float, float, float]:
    """Run up to 12 monthly steps. Returns (new_balance, total_interest_paid, total_paid).

    Loan may pay off mid-year — closed-form geometric solution is unsafe across
    that boundary, so iterate.
    """
    interest_paid = 0.0
    paid = 0.0
    for _ in range(12):
        if balance <= 0:
            return balance, interest_paid, paid
        interest = balance * monthly_rate
        principal = monthly_payment - interest
        if principal >= balance:
            interest_paid += interest
            paid += balance + interest
            return 0.0, interest_paid, paid
        balance -= principal
        interest_paid += interest
        paid += monthly_payment
    return balance, interest_paid, paid


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


def _retirement_age_for(person: PersonInput, default: int) -> int:
    return person.retirement_age if person.retirement_age is not None else default


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
    for liability in plan.liabilities:
        _ensure_finite(liability.principal, f"liability[{liability.id}].principal")
        _ensure_finite(liability.interest_rate, f"liability[{liability.id}].interest_rate")
        if liability.monthly_payment is not None:
            _ensure_finite(liability.monthly_payment, f"liability[{liability.id}].monthly_payment")
    for g in plan.goals:
        _ensure_finite(g.target_amount, f"goal[{g.id}].target_amount")
    a = plan.assumptions
    _ensure_finite(a.inflation_rate, "assumptions.inflation_rate")
    _ensure_finite(a.default_growth_rate, "assumptions.default_growth_rate")
    _ensure_finite(a.property_growth_rate, "assumptions.property_growth_rate")
    _ensure_finite(a.earnings_growth, "assumptions.earnings_growth")
    _ensure_finite(a.state_pension_annual_amount, "assumptions.state_pension_annual_amount")
    _ensure_finite(a.state_pension_escalation_rate, "assumptions.state_pension_escalation_rate")


def simulate(plan: PlanInput) -> list[YearRow]:
    _validate_plan_input(plan)
    tax_config = _resolve_tax_config(plan.tax_config)
    years = range(plan.base_year, plan.base_year + plan.projection_years)
    states: dict[int, AssetState] = {
        a.id: AssetState(
            kind=a.kind,
            balance=a.value,
            growth=a.growth_rate,
            basis=a.cost_basis,
            acquired=a.acquired_year if a.acquired_year is not None else plan.base_year,
            owner=a.owner_person_id,
        )
        for a in plan.assets
    }

    liability_balances: dict[int, float] = {
        liability.id: liability.principal
        for liability in plan.liabilities
        if liability.start_year <= plan.base_year
    }
    retired_persons: set[int] = set()  # person ids who have already crystallised
    deceased_persons: set[int] = set()  # person ids who have already died
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

    _COST_BEARING_GOAL_KINDS = {"milestone", "gift", "pre_retirement_spend", "education"}

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
        for st in states.values():
            st.balance *= 1.0 + st.growth

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
        estate_transfers_year: dict[int, float] = {}

        for person in plan.people:
            age = ages[person.id]
            if age < person.life_expectancy or person.id in deceased_persons:
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

            cat_paid_year += person_cat
            notes.append(
                f"{person.name} passes: estate EUR {estate_value:,.0f}"
                + (f", CAT EUR {person_cat:,.0f}." if person_cat > 0 else ".")
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

        for person in plan.people:
            age = ages[person.id]
            # Skip persons who have died (this year's death is handled in step 2c above).
            if age >= person.life_expectancy:
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
                # pension and ARF drawdowns are auto-injected elsewhere.
                if is_retired_now and inc.kind in ("employment", "self_employment"):
                    continue
                amt = _escalate(inc.gross_amount, inc.escalation_rate, year - inc.start_year)
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
                    arf_amount = pot - lump_sum
                    crystallised_lump_sum = lump_sum
                    crystallised_lump_sum_tax = pension_ie.lump_sum_tax(lump_sum, tax_config)
                    net_lump_sum = lump_sum - crystallised_lump_sum_tax

                    # Zero out pension wrappers owned by this person.
                    for st in states.values():
                        if st.kind in _PENSION_WRAPPERS and st.owner == person.id:
                            st.balance = 0.0

                    states[_cash_target()].balance += net_lump_sum
                    states[_person_arf_target(person.id)].balance += arf_amount

                    notes.append(
                        f"{person.name} retires: pot EUR {pot:,.0f} → lump sum EUR {lump_sum:,.0f} "
                        f"(tax EUR {crystallised_lump_sum_tax:,.0f}) + ARF EUR {arf_amount:,.0f}."
                    )
                retired_persons.add(person.id)

            pension_lump_sum_total += crystallised_lump_sum
            pension_lump_sum_tax_total += crystallised_lump_sum_tax

            # 3d. ARF imputed minimum drawdown (post-retirement).
            arf_drawdown = 0.0
            if is_retired_now:
                arf_total = sum(
                    st.balance
                    for st in states.values()
                    if st.kind == "arf" and st.owner == person.id
                )
                pct = pension_ie.arf_minimum_drawdown_pct(age, arf_total, tax_config)
                if pct > 0 and arf_total > 0:
                    arf_drawdown = arf_total * pct
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

            # 3f. Tax computation.
            taxable_for_it = max(0.0, earned_for_it - pension_contribution) + arf_drawdown + state_pension_amt
            taxable_for_usc = max(0.0, earned_for_usc) + arf_drawdown + state_pension_amt
            taxable_for_prsi = earned_for_prsi  # ARF + state pension exempt

            status = _filing_status_for_person(
                person,
                plan.people,
                any_two_income,
                plan.filing_status,
                age=age,
                is_paye_employee=has_paye_income or not has_self_employment or is_retired_now,
            )

            it, _band = tax_ie.income_tax(taxable_for_it, status, tax_config)
            u = tax_ie.usc(taxable_for_usc, tax_config)
            p_prsi = tax_ie.prsi(
                taxable_for_prsi,
                is_paye=status.is_paye_employee,
                tax_config=tax_config,
            )
            total = it + u + p_prsi

            person_rows.append(
                PersonYear(
                    person_id=person.id,
                    name=person.name,
                    age=age,
                    gross_income=round(taxable_for_it, 2),
                    income_tax=round(it, 2),
                    usc=round(u, 2),
                    prsi=round(p_prsi, 2),
                    net_income=round(taxable_for_it - total, 2),
                )
            )

        gross_income_total = sum(pr.gross_income for pr in person_rows)
        total_it = sum(pr.income_tax for pr in person_rows)
        total_usc = sum(pr.usc for pr in person_rows)
        total_prsi = sum(pr.prsi for pr in person_rows)
        total_tax = total_it + total_usc + total_prsi
        net_income = gross_income_total - total_tax

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
            bal = liability_balances[liability.id]
            if bal <= 0:
                continue
            monthly_rate = liability.interest_rate / 12.0
            new_bal, _interest_paid, paid = _amortise_year(
                bal, monthly_rate, liability.monthly_payment
            )
            liability_balances[liability.id] = new_bal
            debt_service += paid
        if debt_service > 0:
            expenses_by_category["debt_service"] = (
                expenses_by_category.get("debt_service", 0.0) + debt_service
            )

        expenses_total = sum(expenses_by_category.values())

        # ----- 5. Cash flow -----
        # Pension contribution is funded out of gross earnings (already deducted from net
        # income via the IT computation). Lump sum tax is a separate one-shot bill.
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
                # Grade against accessible (non-locked-pension) net worth so a
                # high PRSA balance doesn't falsely satisfy a pre-retirement target.
                status = "met" if accessible_net_worth >= g.target_amount else "below_target"
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
                goal_status=goal_status,
                notes=notes,
                cat_paid=round(cat_paid_year, 2),
                estate_transfers=estate_transfers_year,
                asset_contributions=round(asset_contributions_total, 2),
                had_shortfall=had_shortfall,
            )
        )

    return rows
