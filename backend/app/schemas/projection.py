from pydantic import BaseModel


class PersonYearOut(BaseModel):
    person_id: int
    name: str
    age: int
    gross_income: float
    income_tax: float
    usc: float
    prsi: float
    net_income: float


class YearRowOut(BaseModel):
    year: int
    ages: dict[int, int]
    persons: list[PersonYearOut]
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
    accessible_net_worth: float = 0.0
    liquid_assets: float = 0.0
    liability_balances: dict[int, float] = {}
    debt_outstanding: float = 0.0
    investment_tax: float = 0.0
    realised_gains: float = 0.0
    pension_contributions: float = 0.0
    employer_pension_contributions: float = 0.0
    pension_lump_sum: float = 0.0
    pension_lump_sum_tax: float = 0.0
    arf_drawdowns: float = 0.0
    state_pension_total: float = 0.0
    goal_status: dict[int, str] = {}
    notes: list[str]
    cat_paid: float = 0.0
    estate_transfers: dict[int, float] = {}
    asset_contributions: float = 0.0
    had_shortfall: bool = False
    benefits_in_kind_total: float = 0.0
    protection_premiums_total: float = 0.0
    life_cover_payout: float = 0.0
    cover_gap: float = 0.0


class MonteCarloYearRow(BaseModel):
    year: int
    p5: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float


class MonteCarloResponse(BaseModel):
    runs: int
    years: list[MonteCarloYearRow]
    shortfall_probability: float
    median_final_net_worth: float


class ProjectionSummary(BaseModel):
    plan_id: int
    base_year: int
    projection_years: int
    final_net_worth: float
    peak_net_worth: float
    peak_net_worth_year: int
    first_shortfall_year: int | None
    total_lifetime_tax: float


class ProjectionResponse(BaseModel):
    summary: ProjectionSummary
    years: list[YearRowOut]
