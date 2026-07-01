from pydantic import BaseModel, ConfigDict, Field


class DBPensionCreate(BaseModel):
    person_id: int
    name: str = Field(min_length=1, max_length=200)
    accrual_rate: float = Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False)
    service_years: float = Field(default=0.0, ge=0.0, le=60.0, allow_inf_nan=False)
    final_salary: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    revaluation_rate: float = Field(default=0.0, ge=0.0, le=0.2, allow_inf_nan=False)
    normal_retirement_age: int = Field(default=65, ge=40, le=85)
    tax_free_lump_sum: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)


class DBPensionUpdate(BaseModel):
    person_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    accrual_rate: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    service_years: float | None = Field(default=None, ge=0.0, le=60.0, allow_inf_nan=False)
    final_salary: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    revaluation_rate: float | None = Field(default=None, ge=0.0, le=0.2, allow_inf_nan=False)
    normal_retirement_age: int | None = Field(default=None, ge=40, le=85)
    tax_free_lump_sum: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)


class DBPensionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    person_id: int
    name: str
    accrual_rate: float
    service_years: float
    final_salary: float
    revaluation_rate: float
    normal_retirement_age: int
    tax_free_lump_sum: float
