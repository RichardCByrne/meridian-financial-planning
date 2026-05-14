from pydantic import BaseModel, ConfigDict, Field

EXPENSE_CATEGORIES = ("basic", "discretionary", "single_year", "legacy")


class ExpenseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(pattern="^(basic|discretionary|single_year|legacy)$")
    amount: float = Field(ge=0, allow_inf_nan=False)
    start_year: int = Field(ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)
    escalation_rate: float = Field(default=0.0, ge=-0.5, le=0.5, allow_inf_nan=False)
    owner_person_id: int | None = None


class ExpenseUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    start_year: int | None = Field(default=None, ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)
    escalation_rate: float | None = Field(default=None, ge=-0.5, le=0.5, allow_inf_nan=False)
    owner_person_id: int | None = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    name: str
    category: str
    amount: float
    start_year: int
    end_year: int | None
    escalation_rate: float
    owner_person_id: int | None
