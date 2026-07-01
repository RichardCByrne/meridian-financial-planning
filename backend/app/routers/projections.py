import logging
import time
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.engine.scenario import apply_overrides
from app.auth import get_current_user, require_plan_access
from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    BenefitInput,
    BequestInput,
    ChildInput,
    ExpenseInput,
    GoalInput,
    IncomeInput,
    DBPensionInput,
    LiabilityAdjustmentInput,
    LiabilityInput,
    LifePolicyInput,
    PersonInput,
    PlanInput,
    simulate,
)
from app.engine import montecarlo as _mc
from app.engine.tax_config import TaxConfig
from app.models import (
    Assumptions,
    Benefit,
    Bequest,
    Child,
    IncomeSource,
    DBPension,
    Liability,
    LifePolicy,
    Plan,
    Scenario,
    TaxConfigRow,
    User,
)
from app.schemas.projection import (
    MonteCarloResponse,
    MonteCarloYearRow,
    ProjectionResponse,
    ProjectionSummary,
    YearRowOut,
)

router = APIRouter(tags=["projection"])


# --- Monte-Carlo response cache --------------------------------------------
#
# Each call to /projection/montecarlo runs `n` independent simulations, which
# is the heaviest endpoint in the app. The same (plan, scenario, n, seed)
# tuple is requested repeatedly when the user toggles the fan-chart on/off
# or changes an unrelated chart selector, so caching the response for a
# short window cuts that cost dramatically.
#
# Time-based TTL only — we do not invalidate on plan mutation. 60s is short
# enough that stale results between an edit and the next chart fetch are
# acceptable; the deterministic /projection endpoint reflects edits
# immediately.

_MC_CACHE_TTL_SECONDS = 60.0
_mc_cache: dict[tuple[int, int | None, int, int | None], tuple[float, "MonteCarloResponse"]] = {}


def _mc_cache_get(key: tuple[int, int | None, int, int | None]) -> "MonteCarloResponse | None":
    entry = _mc_cache.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if expires_at < time.monotonic():
        _mc_cache.pop(key, None)
        return None
    return value


def _mc_cache_set(key: tuple[int, int | None, int, int | None], value: "MonteCarloResponse") -> None:
    _mc_cache[key] = (time.monotonic() + _MC_CACHE_TTL_SECONDS, value)


def _mc_cache_clear() -> None:
    """Test hook — production code should never call this."""
    _mc_cache.clear()


def _load_plan_input(plan: Plan, db: Session) -> PlanInput:
    people = [
        PersonInput(
            id=p.id,
            name=p.name,
            dob=p.dob,
            is_primary=p.is_primary,
            life_expectancy=p.life_expectancy,
            death_year=p.death_year,
            retirement_age=p.retirement_age,
            claims_rent_credit=p.claims_rent_credit,
            lump_sum_pct=p.lump_sum_pct,
            prsi_weeks_at_base_year=p.prsi_weeks_at_base_year,
            homecaring_weeks_at_base_year=p.homecaring_weeks_at_base_year,
            arf_target_drawdown_pct=p.arf_target_drawdown_pct,
            pension_option=p.pension_option,
            annuity_rate=p.annuity_rate,
        )
        for p in plan.people
    ]
    person_ids = [p.id for p in plan.people]
    incomes_raw = list(
        db.execute(
            select(IncomeSource).where(IncomeSource.person_id.in_(person_ids or [-1]))
        ).scalars()
    )
    incomes = [
        IncomeInput(
            id=i.id,
            person_id=i.person_id,
            kind=i.kind,
            name=i.name,
            gross_amount=i.gross_amount,
            start_year=i.start_year,
            end_year=i.end_year,
            escalation_rate=i.escalation_rate,
            pays_prsi=i.pays_prsi,
            pays_usc=i.pays_usc,
            pension_contribution_pct=i.pension_contribution_pct,
            employer_pension_contribution_pct=i.employer_pension_contribution_pct,
            is_bonus=i.is_bonus,
        )
        for i in incomes_raw
    ]
    expenses = [
        ExpenseInput(
            id=e.id,
            name=e.name,
            category=e.category,
            amount=e.amount,
            start_year=e.start_year,
            end_year=e.end_year,
            escalation_rate=e.escalation_rate,
        )
        for e in plan.expenses
    ]
    assets = [
        AssetInput(
            id=a.id,
            name=a.name,
            kind=a.kind,
            value=a.value,
            growth_rate=a.growth_rate,
            cost_basis=a.cost_basis,
            acquired_year=a.acquired_year,
            owner_person_id=a.owner_person_id,
            annual_contribution=a.annual_contribution,
            contribution_pct_of_net_income=a.contribution_pct_of_net_income,
            contribution_pct_of_gross_income=a.contribution_pct_of_gross_income,
            contribution_start_year=a.contribution_start_year,
            contribution_end_year=a.contribution_end_year,
            avc_annual=a.avc_annual,
            avc_pct_of_gross=a.avc_pct_of_gross,
            purchase_year=a.purchase_year,
            deposit=a.deposit,
            disposal_year=a.disposal_year,
            linked_liability_id=a.linked_liability_id,
            stamp_duty_pct=a.stamp_duty_pct,
            selling_cost_pct=a.selling_cost_pct,
            annual_charge_pct=a.annual_charge_pct,
        )
        for a in plan.assets
    ]
    liabilities = [
        LiabilityInput(
            id=liability.id,
            name=liability.name,
            kind=liability.kind,
            principal=liability.principal,
            interest_rate=liability.interest_rate,
            term_months=liability.term_months,
            start_year=liability.start_year,
            monthly_payment=liability.monthly_payment,
            monthly_overpayment=liability.monthly_overpayment,
            adjustments=[
                LiabilityAdjustmentInput(
                    id=adj.id,
                    kind=adj.kind,
                    effective_year=adj.effective_year,
                    value=adj.value,
                )
                for adj in liability.adjustments
            ],
        )
        for liability in plan.liabilities
    ]
    goals = [
        GoalInput(
            id=g.id,
            kind=g.kind,
            name=g.name,
            target_amount=g.target_amount,
            target_year=g.target_year,
            linked_person_id=g.linked_person_id,
        )
        for g in plan.goals
    ]
    a = plan.assumptions
    assumptions = AssumptionsInput(
        inflation_rate=a.inflation_rate if a else 0.025,
        default_growth_rate=a.default_growth_rate if a else 0.05,
        property_growth_rate=a.property_growth_rate if a else 0.03,
        earnings_growth=a.earnings_growth if a else 0.03,
        state_pension_age=a.state_pension_age if a else 66,
        state_pension_annual_amount=a.state_pension_annual_amount if a else 15_563.0,
        state_pension_escalation_rate=a.state_pension_escalation_rate if a else 0.015,
    )
    bequests_raw = list(
        db.execute(select(Bequest).where(Bequest.plan_id == plan.id)).scalars()
    )
    bequests = [
        BequestInput(
            id=b.id,
            from_person_id=b.from_person_id,
            to_person_id=b.to_person_id,
            cat_group=b.cat_group,
            share_pct=b.share_pct,
        )
        for b in bequests_raw
    ]
    children_raw = list(
        db.execute(select(Child).where(Child.plan_id == plan.id)).scalars()
    )
    children = [
        ChildInput(
            id=c.id,
            name=c.name,
            dob=c.dob,
            primary_carer_id=c.primary_carer_id,
            childcare_annual=c.childcare_annual,
            primary_annual=c.primary_annual,
            secondary_annual=c.secondary_annual,
            secondary_is_private=c.secondary_is_private,
            secondary_private_fee_annual=c.secondary_private_fee_annual,
            everyday_annual=c.everyday_annual,
        )
        for c in children_raw
    ]
    benefits_raw = list(
        db.execute(select(Benefit).where(Benefit.plan_id == plan.id)).scalars()
    )
    benefits = [
        BenefitInput(
            id=b.id,
            person_id=b.person_id,
            kind=b.kind,
            name=b.name,
            start_year=b.start_year,
            end_year=b.end_year,
            escalation_rate=b.escalation_rate,
            amount=b.amount,
            omv=b.omv,
            rate=b.rate,
            loan_is_qualifying=b.loan_is_qualifying,
            relief_adults=b.relief_adults,
            relief_children=b.relief_children,
        )
        for b in benefits_raw
    ]
    life_policies_raw = list(
        db.execute(select(LifePolicy).where(LifePolicy.plan_id == plan.id)).scalars()
    )
    life_policies = [
        LifePolicyInput(
            id=lp.id,
            person_id=lp.person_id,
            name=lp.name,
            sum_assured=lp.sum_assured,
            premium_annual=lp.premium_annual,
            start_year=lp.start_year,
            end_year=lp.end_year,
            kind=lp.kind,
        )
        for lp in life_policies_raw
    ]
    db_pensions_raw = list(
        db.execute(select(DBPension).where(DBPension.plan_id == plan.id)).scalars()
    )
    db_pensions = [
        DBPensionInput(
            id=dp.id,
            person_id=dp.person_id,
            name=dp.name,
            accrual_rate=dp.accrual_rate,
            service_years=dp.service_years,
            final_salary=dp.final_salary,
            revaluation_rate=dp.revaluation_rate,
            normal_retirement_age=dp.normal_retirement_age,
            tax_free_lump_sum=dp.tax_free_lump_sum,
        )
        for dp in db_pensions_raw
    ]
    tax_config = _resolve_plan_tax_config(plan, db)
    return PlanInput(
        base_year=plan.base_year,
        projection_years=plan.projection_years,
        people=people,
        incomes=incomes,
        expenses=expenses,
        assets=assets,
        liabilities=liabilities,
        goals=goals,
        bequests=bequests,
        children=children,
        benefits=benefits,
        life_policies=life_policies,
        db_pensions=db_pensions,
        assumptions=assumptions,
        tax_config=tax_config,
        filing_status=plan.filing_status,
    )


def _resolve_plan_tax_config(plan: Plan, db: Session) -> TaxConfig | None:
    """Look up the plan's TaxConfigRow (if pinned) and convert to a TaxConfig
    dataclass. Returns None if the plan has no pin — the simulator falls back
    to the seeded official internally."""
    if plan.tax_config_id is None:
        return None
    row = db.get(TaxConfigRow, plan.tax_config_id)
    if row is None:
        return None
    try:
        return TaxConfig.from_dict(row.config_json)
    except Exception:
        logging.getLogger(__name__).exception(
            "Failed to load TaxConfig id=%s for plan id=%s — falling back to seeded official",
            plan.tax_config_id,
            plan.id,
        )
        return None


def _load_plan(plan_id: int, db: Session) -> Plan:
    plan = db.execute(
        select(Plan)
        .where(Plan.id == plan_id)
        .options(
            selectinload(Plan.people),
            selectinload(Plan.expenses),
            selectinload(Plan.assets),
            selectinload(Plan.liabilities).selectinload(Liability.adjustments),
            selectinload(Plan.goals),
            selectinload(Plan.assumptions),
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.assumptions is None:
        plan.assumptions = Assumptions(plan_id=plan.id)
        db.add(plan.assumptions)
        db.commit()
    return plan


def _load_scenario(plan_id: int, scenario_id: int | None, db: Session) -> Scenario | None:
    if scenario_id is None:
        return None
    s = db.get(Scenario, scenario_id)
    if s is None or s.plan_id != plan_id:
        raise HTTPException(status_code=404, detail="Scenario not found for this plan")
    return s


def _build_response(plan: Plan, scenario: Scenario | None, db: Session) -> ProjectionResponse:
    plan_input = _load_plan_input(plan, db)
    if scenario is not None:
        plan_input = apply_overrides(plan_input, scenario.overrides_json)
    rows = simulate(plan_input)

    final_nw = rows[-1].net_worth if rows else 0.0
    peak = max(rows, key=lambda r: r.net_worth) if rows else None
    first_shortfall = next(
        (r.year for r in rows if r.had_shortfall),
        None,
    )
    lifetime_tax = sum(r.total_tax + r.investment_tax for r in rows)

    summary = ProjectionSummary(
        plan_id=plan.id,
        base_year=plan.base_year,
        projection_years=plan.projection_years,
        final_net_worth=round(final_nw, 2),
        peak_net_worth=round(peak.net_worth if peak else 0.0, 2),
        peak_net_worth_year=peak.year if peak else plan.base_year,
        first_shortfall_year=first_shortfall,
        total_lifetime_tax=round(lifetime_tax, 2),
    )
    return ProjectionResponse(
        summary=summary,
        years=[YearRowOut(**asdict(r)) for r in rows],
    )


@router.get("/plans/{plan_id}/projection", response_model=ProjectionResponse)
def get_projection(
    plan_id: int,
    scenario_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectionResponse:
    require_plan_access(plan_id, user, db, min_role="viewer")
    plan = _load_plan(plan_id, db)
    scenario = _load_scenario(plan_id, scenario_id, db)
    return _build_response(plan, scenario, db)


@router.get("/plans/{plan_id}/compare")
def compare_projections(
    plan_id: int,
    a: int | None = Query(default=None, description="Scenario id for series A; null = base"),
    b: int | None = Query(default=None, description="Scenario id for series B; null = base"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Run the simulator twice and return aligned results plus a per-year delta strip.

    Either side may be `null` to use the base plan; passing the same scenario id
    on both sides is allowed and produces a flat zero delta.
    """
    require_plan_access(plan_id, user, db, min_role="viewer")
    plan = _load_plan(plan_id, db)
    scen_a = _load_scenario(plan_id, a, db)
    scen_b = _load_scenario(plan_id, b, db)
    proj_a = _build_response(plan, scen_a, db)
    proj_b = _build_response(plan, scen_b, db)

    delta = [
        {
            "year": ya.year,
            "net_worth_delta": round(yb.net_worth - ya.net_worth, 2),
            "net_income_delta": round(yb.net_income_total - ya.net_income_total, 2),
            "total_tax_delta": round(
                (yb.total_tax + yb.investment_tax) - (ya.total_tax + ya.investment_tax), 2
            ),
            "expenses_delta": round(yb.expenses_total - ya.expenses_total, 2),
        }
        for ya, yb in zip(proj_a.years, proj_b.years)
    ]
    return {
        "a": {"scenario_id": a, "scenario_name": scen_a.name if scen_a else "Base", "projection": proj_a},
        "b": {"scenario_id": b, "scenario_name": scen_b.name if scen_b else "Base", "projection": proj_b},
        "delta": delta,
    }


@router.get("/plans/{plan_id}/projection/montecarlo", response_model=MonteCarloResponse)
def get_montecarlo(
    plan_id: int,
    n: int = Query(default=200, ge=10, le=1000, description="Number of simulation runs"),
    scenario_id: int | None = Query(default=None),
    seed: int | None = Query(default=None, description="Optional RNG seed for reproducible runs"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonteCarloResponse:
    """Run N perturbed simulations and return per-year net-worth percentile bands.

    Each run perturbs asset growth rates and macro assumptions once (persistent
    shock model). Returns p5 / p10 / p25 / p50 / p75 / p90 / p95 bands plus
    the probability of at least one shortfall occurring across all runs.
    """
    require_plan_access(plan_id, user, db, min_role="viewer")
    cache_key = (plan_id, scenario_id, n, seed)
    cached = _mc_cache_get(cache_key)
    if cached is not None:
        return cached

    plan = _load_plan(plan_id, db)
    scenario = _load_scenario(plan_id, scenario_id, db)
    plan_input = _load_plan_input(plan, db)
    if scenario is not None:
        plan_input = apply_overrides(plan_input, scenario.overrides_json)

    result = _mc.run(plan_input, n_runs=n, seed=seed)
    response = MonteCarloResponse(
        runs=result.runs,
        years=[
            MonteCarloYearRow(
                year=y.year,
                p5=y.p5,
                p10=y.p10,
                p25=y.p25,
                p50=y.p50,
                p75=y.p75,
                p90=y.p90,
                p95=y.p95,
            )
            for y in result.years
        ],
        shortfall_probability=result.shortfall_probability,
        median_final_net_worth=result.median_final_net_worth,
    )
    _mc_cache_set(cache_key, response)
    return response
