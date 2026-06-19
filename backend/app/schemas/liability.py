from pydantic import BaseModel, ConfigDict, Field

LIABILITY_KINDS = ("mortgage", "loan")
ADJUSTMENT_KINDS = ("rate", "overpayment", "lump_sum")


class LiabilityAdjustmentCreate(BaseModel):
    # "rate" → new annual rate (0–1 fraction); "overpayment" → new €/mo;
    # "lump_sum" → one-off € off the balance in effective_year.
    kind: str = Field(pattern="^(rate|overpayment|lump_sum)$")
    effective_year: int = Field(ge=1900, le=2200)
    value: float = Field(ge=0, le=10_000_000, allow_inf_nan=False)


class LiabilityAdjustmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    liability_id: int
    kind: str
    effective_year: int
    value: float


class LiabilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(mortgage|loan)$")
    principal: float = Field(gt=0, allow_inf_nan=False)
    interest_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    term_months: int = Field(gt=0, le=600)
    start_year: int = Field(ge=1900, le=2200)
    monthly_payment: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    monthly_overpayment: float = Field(default=0.0, ge=0, le=100_000, allow_inf_nan=False)
    adjustments: list[LiabilityAdjustmentCreate] = Field(default_factory=list)


class LiabilityUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None
    principal: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    interest_rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    term_months: int | None = Field(default=None, gt=0, le=600)
    start_year: int | None = Field(default=None, ge=1900, le=2200)
    monthly_payment: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    monthly_overpayment: float | None = Field(default=None, ge=0, le=100_000, allow_inf_nan=False)
    # When provided, replaces the full adjustment set. Omit to leave unchanged.
    adjustments: list[LiabilityAdjustmentCreate] | None = None


class LiabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    name: str
    kind: str
    principal: float
    interest_rate: float
    term_months: int
    start_year: int
    monthly_payment: float
    monthly_overpayment: float = 0.0
    adjustments: list[LiabilityAdjustmentRead] = Field(default_factory=list)
