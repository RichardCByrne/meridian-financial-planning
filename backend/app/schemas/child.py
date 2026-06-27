from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator


_MAX_AGE_YEARS = 30


def _validate_dob(value: date | None) -> date | None:
    if value is None:
        return value
    today = date.today()
    # Future births are unrestricted: users plan children years ahead, before
    # conception. The projection only counts a child once their birth year is
    # reached, so a far-future dob is harmless. Past dates keep a sanity cap.
    if value < today - timedelta(days=_MAX_AGE_YEARS * 366):
        raise ValueError(f"dob cannot be more than {_MAX_AGE_YEARS} years ago")
    return value


class ChildCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dob: date
    primary_carer_id: int | None = None
    childcare_annual: float = Field(default=0.0, ge=0.0)
    primary_annual: float = Field(default=0.0, ge=0.0)
    secondary_annual: float = Field(default=0.0, ge=0.0)
    secondary_is_private: bool = False
    secondary_private_fee_annual: float = Field(default=0.0, ge=0.0)
    everyday_annual: float = Field(default=0.0, ge=0.0)

    @field_validator("dob")
    @classmethod
    def _check_dob(cls, value: date) -> date:
        return _validate_dob(value)  # type: ignore[return-value]


class ChildUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dob: date | None = None
    primary_carer_id: int | None = None
    childcare_annual: float | None = Field(default=None, ge=0.0)
    primary_annual: float | None = Field(default=None, ge=0.0)
    secondary_annual: float | None = Field(default=None, ge=0.0)
    secondary_is_private: bool | None = None
    secondary_private_fee_annual: float | None = Field(default=None, ge=0.0)
    everyday_annual: float | None = Field(default=None, ge=0.0)

    @field_validator("dob")
    @classmethod
    def _check_dob(cls, value: date | None) -> date | None:
        return _validate_dob(value)


class ChildRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    name: str
    dob: date
    primary_carer_id: int | None
    childcare_annual: float
    primary_annual: float
    secondary_annual: float
    secondary_is_private: bool
    secondary_private_fee_annual: float
    everyday_annual: float
