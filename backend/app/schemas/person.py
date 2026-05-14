from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator


_MAX_AGE_YEARS = 120


def _validate_dob(value: date | None) -> date | None:
    if value is None:
        return value
    today = date.today()
    if value > today:
        raise ValueError("dob cannot be in the future")
    # 120-year cap mirrors life_expectancy; reject obviously bogus historical dates.
    if value < today - timedelta(days=_MAX_AGE_YEARS * 366):
        raise ValueError(f"dob cannot be more than {_MAX_AGE_YEARS} years ago")
    return value


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dob: date
    is_primary: bool = False
    life_expectancy: int = Field(default=90, ge=50, le=120)
    gender_for_state_pension: str | None = None
    retirement_age: int | None = Field(default=None, ge=40, le=85)
    claims_rent_credit: bool = False

    @field_validator("dob")
    @classmethod
    def _check_dob(cls, value: date) -> date:
        return _validate_dob(value)  # type: ignore[return-value]


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dob: date | None = None
    is_primary: bool | None = None
    life_expectancy: int | None = Field(default=None, ge=50, le=120)
    gender_for_state_pension: str | None = None
    retirement_age: int | None = Field(default=None, ge=40, le=85)
    claims_rent_credit: bool | None = None

    @field_validator("dob")
    @classmethod
    def _check_dob(cls, value: date | None) -> date | None:
        return _validate_dob(value)


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
