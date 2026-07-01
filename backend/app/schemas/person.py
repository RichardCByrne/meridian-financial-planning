from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_MAX_AGE_YEARS = 120

PensionOption = Literal["arf", "annuity", "taxable_lump_sum"]


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
    death_year: int | None = Field(default=None, ge=1900, le=2200)
    gender_for_state_pension: str | None = None
    retirement_age: int | None = Field(default=None, ge=40, le=85)
    claims_rent_credit: bool = False
    lump_sum_pct: float = Field(default=0.25, ge=0.0, le=0.25)
    prsi_weeks_at_base_year: int = Field(default=2080, ge=0, le=2600)
    homecaring_weeks_at_base_year: int = Field(default=0, ge=0, le=1040)
    arf_target_drawdown_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    pension_option: PensionOption = "arf"
    annuity_rate: float = Field(default=0.04, ge=0.0, le=0.2)

    @field_validator("dob")
    @classmethod
    def _check_dob(cls, value: date) -> date:
        return _validate_dob(value)  # type: ignore[return-value]


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dob: date | None = None
    is_primary: bool | None = None
    life_expectancy: int | None = Field(default=None, ge=50, le=120)
    death_year: int | None = Field(default=None, ge=1900, le=2200)
    gender_for_state_pension: str | None = None
    retirement_age: int | None = Field(default=None, ge=40, le=85)
    claims_rent_credit: bool | None = None
    lump_sum_pct: float | None = Field(default=None, ge=0.0, le=0.25)
    prsi_weeks_at_base_year: int | None = Field(default=None, ge=0, le=2600)
    homecaring_weeks_at_base_year: int | None = Field(default=None, ge=0, le=1040)
    arf_target_drawdown_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    pension_option: PensionOption | None = None
    annuity_rate: float | None = Field(default=None, ge=0.0, le=0.2)

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
    death_year: int | None = None
    gender_for_state_pension: str | None
    retirement_age: int | None
    claims_rent_credit: bool = False
    lump_sum_pct: float = 0.25
    prsi_weeks_at_base_year: int = 2080
    homecaring_weeks_at_base_year: int = 0
    arf_target_drawdown_pct: float | None = None
    pension_option: str = "arf"
    annuity_rate: float = 0.04
