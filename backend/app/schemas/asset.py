from pydantic import BaseModel, ConfigDict, Field

ASSET_KINDS = (
    "cash",
    "deposit",
    "investment_unwrapped",
    "etf_fund",
    "prsa",
    "occupational_pension",
    "arf",
    "property_primary",
    "property_btl",
)


_GROWTH_RATE = Field(default=0.04, ge=-0.5, le=1.0, allow_inf_nan=False)


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(cash|deposit|investment_unwrapped|etf_fund|investment_bond|prsa|occupational_pension|arf|property_primary|property_btl)$")
    value: float = Field(ge=0, allow_inf_nan=False)
    growth_rate: float = _GROWTH_RATE
    owner_person_id: int | None = None
    cost_basis: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    acquired_year: int | None = Field(default=None, ge=1900, le=2200)
    annual_contribution: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    contribution_pct_of_net_income: float = Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False)
    contribution_pct_of_gross_income: float = Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False)
    contribution_start_year: int | None = Field(default=None, ge=1900, le=2200)
    contribution_end_year: int | None = Field(default=None, ge=1900, le=2200)
    avc_annual: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    avc_pct_of_gross: float = Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False)
    purchase_year: int | None = Field(default=None, ge=1900, le=2200)
    deposit: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    disposal_year: int | None = Field(default=None, ge=1900, le=2200)
    linked_liability_id: int | None = None
    stamp_duty_pct: float = Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False)
    selling_cost_pct: float = Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False)
    annual_charge_pct: float = Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False)


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: str | None = None
    value: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    growth_rate: float | None = Field(default=None, ge=-0.5, le=1.0, allow_inf_nan=False)
    owner_person_id: int | None = None
    cost_basis: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    acquired_year: int | None = Field(default=None, ge=1900, le=2200)
    annual_contribution: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    contribution_pct_of_net_income: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    contribution_pct_of_gross_income: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    contribution_start_year: int | None = Field(default=None, ge=1900, le=2200)
    contribution_end_year: int | None = Field(default=None, ge=1900, le=2200)
    avc_annual: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    avc_pct_of_gross: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    purchase_year: int | None = Field(default=None, ge=1900, le=2200)
    deposit: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    disposal_year: int | None = Field(default=None, ge=1900, le=2200)
    linked_liability_id: int | None = None
    stamp_duty_pct: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    selling_cost_pct: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    annual_charge_pct: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    name: str
    kind: str
    value: float
    growth_rate: float
    owner_person_id: int | None
    cost_basis: float
    acquired_year: int | None
    annual_contribution: float
    contribution_pct_of_net_income: float
    contribution_pct_of_gross_income: float
    contribution_start_year: int | None
    contribution_end_year: int | None
    avc_annual: float
    avc_pct_of_gross: float
    purchase_year: int | None
    deposit: float
    disposal_year: int | None
    linked_liability_id: int | None
    stamp_duty_pct: float
    selling_cost_pct: float
    annual_charge_pct: float
