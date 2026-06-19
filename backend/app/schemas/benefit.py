from pydantic import BaseModel, ConfigDict, Field

# Benefit-in-kind kinds. See engine/bik_ie.py for the cash-equivalent maths.
BENEFIT_KINDS = (
    "medical_insurance",
    "company_car",
    "company_van",
    "preferential_loan",
    "other",
)

_KIND_PATTERN = "^(medical_insurance|company_car|company_van|preferential_loan|other)$"


class BenefitCreate(BaseModel):
    person_id: int
    kind: str = Field(pattern=_KIND_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    start_year: int = Field(ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)
    escalation_rate: float = Field(default=0.0, ge=-0.5, le=0.5, allow_inf_nan=False)
    amount: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    omv: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    rate: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    loan_is_qualifying: bool = False
    relief_adults: int = Field(default=1, ge=0, le=20)
    relief_children: int = Field(default=0, ge=0, le=20)


class BenefitUpdate(BaseModel):
    person_id: int | None = None
    kind: str | None = Field(default=None, pattern=_KIND_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    start_year: int | None = Field(default=None, ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)
    escalation_rate: float | None = Field(default=None, ge=-0.5, le=0.5, allow_inf_nan=False)
    amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    omv: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    loan_is_qualifying: bool | None = None
    relief_adults: int | None = Field(default=None, ge=0, le=20)
    relief_children: int | None = Field(default=None, ge=0, le=20)


class BenefitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    person_id: int
    kind: str
    name: str
    start_year: int
    end_year: int | None
    escalation_rate: float
    amount: float
    omv: float
    rate: float
    loan_is_qualifying: bool
    relief_adults: int
    relief_children: int
