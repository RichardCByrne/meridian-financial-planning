from pydantic import BaseModel, ConfigDict, Field

LIABILITY_KINDS = ("mortgage", "loan")


class LiabilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(mortgage|loan)$")
    principal: float = Field(gt=0)
    interest_rate: float = Field(ge=0, le=1)
    term_months: int = Field(gt=0, le=600)
    start_year: int = Field(ge=1900, le=2200)
    monthly_payment: float | None = Field(default=None, ge=0)


class LiabilityUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None
    principal: float | None = Field(default=None, gt=0)
    interest_rate: float | None = Field(default=None, ge=0, le=1)
    term_months: int | None = Field(default=None, gt=0, le=600)
    start_year: int | None = None
    monthly_payment: float | None = Field(default=None, ge=0)


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
