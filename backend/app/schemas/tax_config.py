from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaxConfigRead(BaseModel):
    # populate_by_name + validation_alias lets us READ from the ORM's
    # `config_json` attribute while WRITING the JSON response as `config`.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    is_official: bool
    created_by_user_id: int | None
    created_at: datetime
    config: dict[str, Any] = Field(validation_alias="config_json")


class TaxConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    # Optional: clone from an existing config id; if omitted, the seeded
    # official config is used as the starting point.
    clone_from_id: int | None = None
    # Optional: full config payload (overrides clone_from_id field-by-field).
    config: dict[str, Any] | None = None


class TaxConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: dict[str, Any] | None = None
