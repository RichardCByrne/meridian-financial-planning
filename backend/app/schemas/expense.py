from pydantic import BaseModel, ConfigDict, Field, field_validator

# Only two categories matter financially: single_year (a one-off cost in the
# start year) vs everything else (recurring start→end). basic / discretionary
# are grouping labels for the spend-by-category breakdown — the engine treats
# them identically. "legacy" was a redundant recurring label (no death-linked
# behaviour); it's accepted on input and normalised to "discretionary" for
# back-compat (old clients, imported plans). See migration 0025.
EXPENSE_CATEGORIES = ("basic", "discretionary", "single_year")
_LEGACY_CATEGORIES = ("legacy",)
_CATEGORY_PATTERN = "^(" + "|".join((*EXPENSE_CATEGORIES, *_LEGACY_CATEGORIES)) + ")$"


def _normalise_category(value: str | None) -> str | None:
    if value in _LEGACY_CATEGORIES:
        return "discretionary"
    return value


class ExpenseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(pattern=_CATEGORY_PATTERN)
    amount: float = Field(ge=0, allow_inf_nan=False)
    start_year: int = Field(ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)
    escalation_rate: float = Field(default=0.0, ge=-0.5, le=0.5, allow_inf_nan=False)
    owner_person_id: int | None = None

    @field_validator("category")
    @classmethod
    def _norm(cls, v: str) -> str:
        return _normalise_category(v)  # type: ignore[return-value]


class ExpenseUpdate(BaseModel):
    name: str | None = None
    category: str | None = Field(default=None, pattern=_CATEGORY_PATTERN)
    amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    start_year: int | None = Field(default=None, ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)
    escalation_rate: float | None = Field(default=None, ge=-0.5, le=0.5, allow_inf_nan=False)
    owner_person_id: int | None = None

    @field_validator("category")
    @classmethod
    def _norm(cls, v: str | None) -> str | None:
        return _normalise_category(v)


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
