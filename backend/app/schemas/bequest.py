from pydantic import BaseModel, Field


class BequestCreate(BaseModel):
    from_person_id: int
    to_person_id: int | None = None
    cat_group: str = Field(default="A", pattern="^(A|B|C|exempt)$")
    share_pct: float = Field(..., ge=0.0, le=1.0)
    notes: str | None = None


class BequestUpdate(BaseModel):
    to_person_id: int | None = None
    cat_group: str | None = Field(default=None, pattern="^(A|B|C|exempt)$")
    share_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = None


class BequestRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    plan_id: int
    from_person_id: int
    to_person_id: int | None
    cat_group: str
    share_pct: float
    notes: str | None
