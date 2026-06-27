from pydantic import BaseModel, ConfigDict, Field, field_validator

# Canonical goal kinds — the only three with distinct financial behaviour:
#   spend      — a one-off cost in the target year (graded achieved/missed)
#   net_worth  — a liquid-wealth target to reach by the target year
#   retirement — an informational timeline marker (no cash effect)
GOAL_KINDS = ("retirement", "spend", "net_worth")

# Pre-consolidation kinds that were all financially identical one-off spends.
# Accepted on input (old clients, imported/exported plans) and normalised to
# "spend" so nothing 400s on legacy data. See migration 0024.
_LEGACY_SPEND_KINDS = ("milestone", "education", "gift", "pre_retirement_spend")

_KIND_PATTERN = "^(" + "|".join((*GOAL_KINDS, *_LEGACY_SPEND_KINDS)) + ")$"


def _normalise_kind(value: str | None) -> str | None:
    if value in _LEGACY_SPEND_KINDS:
        return "spend"
    return value


class GoalCreate(BaseModel):
    kind: str = Field(pattern=_KIND_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    target_amount: float = Field(ge=0, allow_inf_nan=False)
    target_year: int = Field(ge=1900, le=2200)
    linked_person_id: int | None = None
    notes: str | None = None

    @field_validator("kind")
    @classmethod
    def _norm(cls, v: str) -> str:
        return _normalise_kind(v)  # type: ignore[return-value]


class GoalUpdate(BaseModel):
    kind: str | None = Field(default=None, pattern=_KIND_PATTERN)
    name: str | None = None
    target_amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    target_year: int | None = Field(default=None, ge=1900, le=2200)
    linked_person_id: int | None = None
    notes: str | None = None

    @field_validator("kind")
    @classmethod
    def _norm(cls, v: str | None) -> str | None:
        return _normalise_kind(v)


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
