from pydantic import BaseModel, ConfigDict, Field

# Only term life is modelled today; the column/enum leaves room for income
# protection and serious illness later without a migration.
_KIND = Field(default="term_life", pattern="^(term_life)$")


class LifePolicyCreate(BaseModel):
    person_id: int
    name: str = Field(min_length=1, max_length=200)
    kind: str = _KIND
    sum_assured: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    premium_annual: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    start_year: int = Field(..., ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)


class LifePolicyUpdate(BaseModel):
    person_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: str | None = Field(default=None, pattern="^(term_life)$")
    sum_assured: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    premium_annual: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    start_year: int | None = Field(default=None, ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)


class LifePolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    person_id: int
    name: str
    kind: str
    sum_assured: float
    premium_annual: float
    start_year: int
    end_year: int | None
