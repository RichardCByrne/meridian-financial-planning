from pydantic import BaseModel, ConfigDict, Field

GOAL_KINDS = (
    "retirement",
    "pre_retirement_spend",
    "milestone",
    "education",
    "net_worth",
    "gift",
)

_KIND_PATTERN = "^(retirement|pre_retirement_spend|milestone|education|net_worth|gift)$"


class GoalCreate(BaseModel):
    kind: str = Field(pattern=_KIND_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    target_amount: float = Field(ge=0, allow_inf_nan=False)
    target_year: int = Field(ge=1900, le=2200)
    linked_person_id: int | None = None
    notes: str | None = None


class GoalUpdate(BaseModel):
    kind: str | None = Field(default=None, pattern=_KIND_PATTERN)
    name: str | None = None
    target_amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    target_year: int | None = Field(default=None, ge=1900, le=2200)
    linked_person_id: int | None = None
    notes: str | None = None


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    kind: str
    name: str
    target_amount: float
    target_year: int
    linked_person_id: int | None
    notes: str | None
