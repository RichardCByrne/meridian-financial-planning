from pydantic import BaseModel, ConfigDict, Field

INCOME_KINDS = (
    "employment",
    "self_employment",
    "rental",
    "state_pension",
    "private_pension_drawdown",
    "annuity",
    "other",
)


class IncomeSourceCreate(BaseModel):
    kind: str = Field(pattern="^(employment|self_employment|rental|state_pension|private_pension_drawdown|annuity|other)$")
    name: str = Field(min_length=1, max_length=200)
    gross_amount: float = Field(ge=0)
    start_year: int
    end_year: int | None = None
    escalation_rate: float = 0.0
    pays_prsi: bool = True
    pays_usc: bool = True
    pension_contribution_pct: float = Field(default=0.0, ge=0, le=1)
    employer_pension_contribution_pct: float = Field(default=0.0, ge=0, le=1)


class IncomeSourceUpdate(BaseModel):
    kind: str | None = None
    name: str | None = None
    gross_amount: float | None = Field(default=None, ge=0)
    start_year: int | None = None
    end_year: int | None = None
    escalation_rate: float | None = None
    pays_prsi: bool | None = None
    pays_usc: bool | None = None
    pension_contribution_pct: float | None = Field(default=None, ge=0, le=1)
    employer_pension_contribution_pct: float | None = Field(default=None, ge=0, le=1)


class IncomeSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    pension_contribution_pct: float
    employer_pension_contribution_pct: float
