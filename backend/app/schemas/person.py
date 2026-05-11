from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dob: date
    is_primary: bool = False
    life_expectancy: int = Field(default=90, ge=50, le=120)
    gender_for_state_pension: str | None = None
    retirement_age: int | None = Field(default=None, ge=40, le=85)
    claims_rent_credit: bool = False


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dob: date | None = None
    is_primary: bool | None = None
    life_expectancy: int | None = Field(default=None, ge=50, le=120)
    gender_for_state_pension: str | None = None
    retirement_age: int | None = Field(default=None, ge=40, le=85)
    claims_rent_credit: bool | None = None


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    name: str
    dob: date
    is_primary: bool
    life_expectancy: int
    gender_for_state_pension: str | None
    retirement_age: int | None
    claims_rent_credit: bool = False
