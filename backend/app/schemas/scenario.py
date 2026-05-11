from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_scenario_id: int | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class ScenarioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_scenario_id: int | None = None
    overrides: dict[str, Any] | None = None


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    name: str
    parent_scenario_id: int | None
    overrides: dict[str, Any]

    @classmethod
    def from_orm_row(cls, row: Any) -> "ScenarioRead":
        return cls(
            id=row.id,
            plan_id=row.plan_id,
            name=row.name,
            parent_scenario_id=row.parent_scenario_id,
            overrides=row.overrides_json or {},
        )
