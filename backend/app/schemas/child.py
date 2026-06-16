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

    @field_validator("dob")
    @classmethod
    def _check_dob(cls, value: date) -> date:
        return _validate_dob(value)  # type: ignore[return-value]


class ChildUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dob: date | None = None
    primary_carer_id: int | None = None

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
