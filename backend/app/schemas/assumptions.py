from pydantic import BaseModel, ConfigDict, Field


class AssumptionsUpsert(BaseModel):
    inflation_rate: float = Field(default=0.025, ge=-0.05, le=0.5)
    default_growth_rate: float = Field(default=0.05, ge=-0.5, le=0.5)
    property_growth_rate: float = Field(default=0.03, ge=-0.5, le=0.5)
    earnings_growth: float = Field(default=0.03, ge=-0.5, le=0.5)
    state_pension_age: int = Field(default=66, ge=50, le=80)
    # 2026 rate: €299.30/week × 52 = €15,563.60/year (Budget 2026 announced Oct 2025).
    state_pension_annual_amount: float = Field(default=15_563.0, ge=0, le=200_000)
    # Historical CAGR of Irish State Pension (Contributory) 2007–2026: ~1.9% nominal.
    # Decoupled from general inflation — the pension is frequently frozen for years at a time.
    state_pension_escalation_rate: float = Field(default=0.015, ge=0.0, le=0.1)


class AssumptionsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    inflation_rate: float
    default_growth_rate: float
    property_growth_rate: float
    earnings_growth: float
    state_pension_age: int
    state_pension_annual_amount: float
    state_pension_escalation_rate: float
