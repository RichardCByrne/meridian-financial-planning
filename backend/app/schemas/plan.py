from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FilingStatusValue = Literal["single", "married", "cohabiting"]


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_year: int = Field(default=2026, ge=1900, le=2200)
    projection_years: int = Field(default=50, ge=1, le=100)
    tax_config_id: int | None = None
    filing_status: FilingStatusValue | None = None


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    base_year: int | None = Field(default=None, ge=1900, le=2200)
    projection_years: int | None = Field(default=None, ge=1, le=100)
    tax_config_id: int | None = None
    filing_status: FilingStatusValue | None = None
    onboarding_complete: bool | None = None


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_year: int
    projection_years: int
    created_at: datetime
    tax_config_id: int | None = None
    filing_status: FilingStatusValue | None = None
    onboarding_complete: bool = False
