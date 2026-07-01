from datetime import date, datetime

from app.db import Base, utcnow

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Plan-membership roles. Ordered by privilege so we can compare with `index()`.
PLAN_ROLES: tuple[str, ...] = ("viewer", "editor", "owner")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Firebase UID is the source of truth for identity. Unique per user; immutable.
    # In MERIDIAN_DEV_AUTH mode the bypass user has firebase_uid="dev-local".
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    # Unique so one email maps to one account — a second provider for the same
    # (verified) address links to the existing row rather than duplicating it.
    # Nullable: rows without an email (e.g. phone auth) are exempt; both SQLite
    # and Postgres allow multiple NULLs under a unique index.
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    plan_memberships: Mapped[list["PlanMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class PlanMember(Base):
    __tablename__ = "plan_members"
    __table_args__ = (UniqueConstraint("plan_id", "user_id", name="uq_plan_user"),)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # viewer | editor | owner
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    plan: Mapped["Plan"] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="plan_memberships")


class PlanInvite(Base):
    """Share-link invite to a plan.

    The token is the substance of the invite: any signed-in user who knows the
    token can accept (granting them the encoded role) — unless `email` is set,
    in which case only a user whose Firebase identity matches that email may
    accept. `accepted_by_user_id` flips the invite into a consumed state and
    further accept attempts return 410 Gone.
    """

    __tablename__ = "plan_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    plan: Mapped["Plan"] = relationship()


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_year: Mapped[int] = mapped_column(Integer, default=2026, nullable=False)
    projection_years: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    # Phase 11: pin a TaxConfig for this plan. NULL = use the seeded official.
    tax_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("tax_configs.id", ondelete="SET NULL"), nullable=True
    )
    # Phase 14: filing status overrides the auto-detection (1 person → single,
    # 2+ → married). Values: "single" | "married" | "cohabiting". NULL = auto.
    # Cohabiting couples are taxed individually under Irish law — without an
    # explicit override the engine would over-credit them as married.
    filing_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Set true the first time a plan has people + income + assets (the getting-
    # started wizard tasks). Lets the UI skip the first-run stepper outright
    # instead of computing completion on every load (which caused a brief flash).
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    people: Mapped[list["Person"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    assets: Mapped[list["Asset"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    liabilities: Mapped[list["Liability"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    goals: Mapped[list["Goal"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    scenarios: Mapped[list["Scenario"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    assumptions: Mapped["Assumptions | None"] = relationship(
        back_populates="plan", uselist=False, cascade="all, delete-orphan"
    )
    members: Mapped[list[PlanMember]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    bequests: Mapped[list["Bequest"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    children: Mapped[list["Child"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    benefits: Mapped[list["Benefit"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    life_policies: Mapped[list["LifePolicy"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    db_pensions: Mapped[list["DBPension"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Benefit(Base):
    """An employer-provided benefit-in-kind (BIK) attached to a person.

    The cash equivalent is charged to the employee as notional pay (IT + USC +
    PRSI) but is not a cash inflow or a household expense — the employer funds
    it. `kind` selects the cash-equivalent calculation (see engine/bik_ie.py):
    medical_insurance / company_car / company_van / preferential_loan / other.
    Field meaning is kind-dependent (see schemas/benefit.py + BenefitInput).
    """

    __tablename__ = "benefits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Cash equivalent / premium / loan balance, interpreted by kind.
    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Company car/van Original Market Value (cash-equiv = omv × rate).
    omv: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Car BIK %, or the interest rate the employer charges on a preferential loan.
    rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Preferential loan: True = qualifying home loan (lower specified rate).
    loan_is_qualifying: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Medical-insurance relief cap sizing (per adult/child covered).
    relief_adults: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    relief_children: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="benefits")


class LifePolicy(Base):
    """A protection policy on one person (the insured). Currently term life:
    while in force (start_year..end_year) the plan pays `premium_annual` out of
    cash; if the insured dies within the term, `sum_assured` pays out tax-free
    to the survivors' cash. `kind` is reserved for future protection types
    (income protection / serious illness) but only "term_life" pays out today.
    """

    __tablename__ = "life_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), default="term_life", nullable=False)
    sum_assured: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    premium_annual: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL end_year = whole-of-life / open-ended cover.
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="life_policies")


class DBPension(Base):
    """A defined-benefit / final-salary pension promise for one person. Pays a
    guaranteed annual income from normal_retirement_age, computed as
    accrual_rate × service_years × final_salary and indexed by revaluation_rate
    (deferment + in payment). Taxed as PAYE income, PRSI-exempt (like an ARF or
    annuity). An optional tax_free_lump_sum is paid to cash at retirement.
    """

    __tablename__ = "db_pensions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Accrual fraction earned per year of service (e.g. 1/60 ≈ 0.016667).
    accrual_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    service_years: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    final_salary: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Indexation applied both in deferment (to retirement) and in payment.
    revaluation_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    normal_retirement_age: Mapped[int] = mapped_column(Integer, default=65, nullable=False)
    # Optional tax-free lump sum paid at normal_retirement_age (0 = none).
    tax_free_lump_sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="db_pensions")


class Child(Base):
    __tablename__ = "children"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    # Person who receives Child Benefit. NULL = pay to plan's primary person.
    primary_carer_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    # Per-child rearing costs (annual €, 0 = not modelled). The simulator
    # age-gates each against the child's dob using TaxConfig stage boundaries:
    #   childcare_annual         — birth → primary start (creche/pre-school)
    #   primary_annual           — primary start → secondary start
    #   secondary_annual         — secondary start → secondary end (public costs)
    #   secondary_private_fee_annual — added on top of secondary_annual when
    #                              secondary_is_private is set (school fees)
    #   everyday_annual          — birth → secondary end (food/clothes). Opt-in:
    #                              may overlap household expenses, so defaults 0.
    # All escalate by the plan's inflation rate. Third-level/college is modelled
    # via an `education` goal, not here.
    childcare_annual: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    primary_annual: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    secondary_annual: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    secondary_is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    secondary_private_fee_annual: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    everyday_annual: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="children")


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    life_expectancy: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    # Optional planned/what-if death year (protection modelling). When set and
    # earlier than the natural life_expectancy year, the person dies then — their
    # income and BIK stop, pensions/estate transfer to survivors (CAT via the
    # existing estate machinery), and any in-force term-life policy pays out.
    # NULL = die at life_expectancy as before.
    death_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender_for_state_pension: Mapped[str | None] = mapped_column(String(10), nullable=True)
    retirement_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Phase 14: rent tax credit (€1,000/yr from Budget 2024) — only applies to
    # renters paying for their own home. Surfaced as a per-person flag because
    # one spouse may rent their workplace digs while the other doesn't (joint
    # assessment then doubles the value via tax_ie._income_tax).
    claims_rent_credit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Fraction of pension pot taken as tax-free lump sum at retirement.
    # Irish rules cap at 25%; lower values leave more in the ARF.
    lump_sum_pct: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    # PRSI / HomeCaring weeks already accrued before the base year. The
    # simulator accumulates +52/yr while income is being earned (or while a
    # "homecaring" income marker is active). Default seeds reproduce the
    # legacy full-state-pension behaviour.
    prsi_weeks_at_base_year: Mapped[int] = mapped_column(Integer, default=2080, nullable=False)
    homecaring_weeks_at_base_year: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Voluntary ARF drawdown rate (post-retirement). NULL = statutory min only.
    arf_target_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # What happens to the pension pot after the tax-free lump sum at retirement:
    # "arf" (default), "annuity", or "taxable_lump_sum".
    pension_option: Mapped[str] = mapped_column(String, default="arf", nullable=False)
    # Annual annuity income as a fraction of the annuitised pot. Only used when
    # pension_option == "annuity".
    annuity_rate: Mapped[float] = mapped_column(Float, default=0.04, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="people")
    income_sources: Mapped[list["IncomeSource"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )


class IncomeSource(Base):
    __tablename__ = "income_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    gross_amount: Mapped[float] = mapped_column(Float, nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pays_prsi: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pays_usc: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pension_contribution_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    employer_pension_contribution_pct: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    # UI marker: a one-off / annual bonus (still a normal taxable income row).
    # Lets the editor badge it and offer a bonus shortcut; the engine ignores it.
    is_bonus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    person: Mapped[Person] = relationship(back_populates="income_sources")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    owner_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )

    plan: Mapped[Plan] = relationship(back_populates="expenses")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    growth_rate: Mapped[float] = mapped_column(Float, default=0.04, nullable=False)
    owner_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    cost_basis: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    acquired_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_contribution: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contribution_pct_of_net_income: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contribution_pct_of_gross_income: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contribution_start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contribution_end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # AVC (Additional Voluntary Contributions) — pension assets only.
    # Tax-relievable, jointly capped with salary-linked contributions by the age-based limit.
    avc_annual: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avc_pct_of_gross: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Planned property/asset transactions (Phase 1). purchase_year in the future
    # gates the asset (dormant, no value/growth) until then, when `value` becomes
    # its balance and `deposit` is paid out of cash. disposal_year triggers a
    # deliberate full sale into cash. Both NULL = owned from base year, never
    # deliberately sold. Distinct from acquired_year (ETF deemed-disposal clock).
    purchase_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    disposal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Phase 2: the mortgage financing this property (settled on a planned sale)
    # and transaction-cost percentages (stamp duty on purchase, agent/legal fees
    # on sale).
    linked_liability_id: Mapped[int | None] = mapped_column(
        ForeignKey("liabilities.id", ondelete="SET NULL"), nullable=True
    )
    stamp_duty_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    selling_cost_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Total annual product charge (AMC + platform + adviser fee) as a fraction of
    # balance, e.g. 0.015 = 1.5%/yr. Deducted from growth each year — real funds
    # compound net of charges. Default 0.0 leaves existing plans unchanged.
    annual_charge_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="assets")


class Liability(Base):
    __tablename__ = "liabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    principal: Mapped[float] = mapped_column(Float, nullable=False)
    interest_rate: Mapped[float] = mapped_column(Float, nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_payment: Mapped[float] = mapped_column(Float, nullable=False)
    # Extra €/mo applied directly to capital. Banks typically allow ±10% of
    # the contracted payment fee-free. Defaults to 0 for legacy rows.
    monthly_overpayment: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="liabilities")
    adjustments: Mapped[list["LiabilityAdjustment"]] = relationship(
        back_populates="liability",
        cascade="all, delete-orphan",
        order_by="LiabilityAdjustment.effective_year",
    )


class LiabilityAdjustment(Base):
    """Time-keyed change to a liability: a rate step, an overpayment change, or a
    one-off lump-sum capital repayment. Mirrors Voyant's mortgage rate periods /
    overpayment events. `value` is interpreted by `kind`:

    - ``rate``       → new annual interest rate as a fraction (0.055 = 5.5%).
                        Payment is re-amortised over the remaining term.
    - ``overpayment``→ new recurring extra €/mo applied to capital from this year.
    - ``lump_sum``   → one-off € paid off the balance in ``effective_year`` only.
    """

    __tablename__ = "liability_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    liability_id: Mapped[int] = mapped_column(
        ForeignKey("liabilities.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    liability: Mapped[Liability] = relationship(back_populates="adjustments")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_amount: Mapped[float] = mapped_column(Float, nullable=False)
    target_year: Mapped[int] = mapped_column(Integer, nullable=False)
    linked_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="goals")


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_scenario_id: Mapped[int | None] = mapped_column(
        ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True
    )
    overrides_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="scenarios")


class TaxConfigRow(Base):
    """Persisted TaxConfig instance.

    The dataclass payload lives in `config_json` so we don't have to migrate
    the schema every time a new field is added. `is_official=True` marks the
    immutable seeded "Ireland 2026 (official)" row — only owned by the system,
    not editable by users. User-created configs have `created_by_user_id` set
    and `is_official=False`.
    """

    __tablename__ = "tax_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Bequest(Base):
    """Describes how a person's estate should be distributed on death.

    `to_person_id = None` means the share goes to an external beneficiary
    (outside the plan). `cat_group` determines which CAT threshold applies.
    `share_pct` is a fraction of the estate (0.0–1.0); multiple bequests
    for the same `from_person_id` should sum to ≤ 1.0 (remainder leaves
    the plan if under-allocated).
    """

    __tablename__ = "bequests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    to_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    # CAT group: "A" (children/parents), "B" (siblings/descendants), "C" (others), "exempt" (spouse)
    cat_group: Mapped[str] = mapped_column(String(10), nullable=False, default="A")
    share_pct: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped["Plan"] = relationship(back_populates="bequests")


class Assumptions(Base):
    __tablename__ = "assumptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), unique=True
    )
    inflation_rate: Mapped[float] = mapped_column(Float, default=0.025, nullable=False)
    default_growth_rate: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    property_growth_rate: Mapped[float] = mapped_column(Float, default=0.03, nullable=False)
    earnings_growth: Mapped[float] = mapped_column(Float, default=0.03, nullable=False)
    state_pension_age: Mapped[int] = mapped_column(Integer, default=66, nullable=False)
    state_pension_annual_amount: Mapped[float] = mapped_column(
        Float, default=15_563.0, nullable=False
    )
    # Historical CAGR ~1.9% nominal 2007-2026; decoupled from general inflation.
    state_pension_escalation_rate: Mapped[float] = mapped_column(
        Float, default=0.015, nullable=False
    )

    plan: Mapped[Plan] = relationship(back_populates="assumptions")


def register_all_models() -> None:
    """No-op; importing this module is enough to register all tables on Base.metadata."""
    return None


__all__ = [
    "Plan",
    "Person",
    "IncomeSource",
    "Expense",
    "Asset",
    "Liability",
    "Goal",
    "Scenario",
    "Assumptions",
    "User",
    "PlanMember",
    "PlanInvite",
    "TaxConfigRow",
    "Bequest",
    "Benefit",
    "LifePolicy",
    "DBPension",
    "Child",
    "PLAN_ROLES",
    "register_all_models",
]
