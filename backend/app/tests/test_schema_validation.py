"""Schema-level validation tests (QA_FINDINGS V1–V8).

Pure pydantic — no FastAPI/DB needed. Confirms bounds reject obviously bad
input at the API boundary instead of letting NaN/inf/garbage years flow into
the engine.
"""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.goal import GoalCreate, GoalUpdate
from app.schemas.income import IncomeSourceCreate, IncomeSourceUpdate
from app.schemas.person import PersonCreate, PersonUpdate
from app.schemas.plan import PlanCreate, PlanUpdate


# ---------- PlanCreate / PlanUpdate (V1) ----------


@pytest.mark.parametrize("year", [1899, 2201, -1, 9999])
def test_plan_create_rejects_out_of_range_base_year(year: int) -> None:
    with pytest.raises(ValidationError):
        PlanCreate(name="x", base_year=year)


@pytest.mark.parametrize("year", [1900, 2026, 2200])
def test_plan_create_accepts_in_range_base_year(year: int) -> None:
    p = PlanCreate(name="x", base_year=year)
    assert p.base_year == year


def test_plan_update_rejects_out_of_range_base_year() -> None:
    with pytest.raises(ValidationError):
        PlanUpdate(base_year=3000)


# ---------- IncomeSource (V2–V4) ----------


def _income_kwargs(**overrides):
    base = dict(
        kind="employment",
        name="Salary",
        gross_amount=50_000,
        start_year=2026,
        end_year=2060,
        escalation_rate=0.03,
    )
    base.update(overrides)
    return base


@pytest.mark.parametrize("year", [1899, 2201])
def test_income_rejects_out_of_range_start_year(year: int) -> None:
    with pytest.raises(ValidationError):
        IncomeSourceCreate(**_income_kwargs(start_year=year))


@pytest.mark.parametrize("year", [1899, 2201])
def test_income_rejects_out_of_range_end_year(year: int) -> None:
    with pytest.raises(ValidationError):
        IncomeSourceCreate(**_income_kwargs(end_year=year))


@pytest.mark.parametrize("rate", [-0.6, 0.51, 1.0, -2.0])
def test_income_rejects_out_of_range_escalation_rate(rate: float) -> None:
    with pytest.raises(ValidationError):
        IncomeSourceCreate(**_income_kwargs(escalation_rate=rate))


@pytest.mark.parametrize("rate", [-0.5, 0.0, 0.5])
def test_income_accepts_boundary_escalation_rate(rate: float) -> None:
    inc = IncomeSourceCreate(**_income_kwargs(escalation_rate=rate))
    assert inc.escalation_rate == rate


def test_income_update_rejects_bad_escalation_rate() -> None:
    with pytest.raises(ValidationError):
        IncomeSourceUpdate(escalation_rate=2.0)


# ---------- Expense (V5–V6) ----------


def _expense_kwargs(**overrides):
    base = dict(
        name="Rent",
        category="basic",
        amount=12_000,
        start_year=2026,
        end_year=2050,
        escalation_rate=0.02,
    )
    base.update(overrides)
    return base


@pytest.mark.parametrize("year", [1800, 2300])
def test_expense_rejects_out_of_range_start_year(year: int) -> None:
    with pytest.raises(ValidationError):
        ExpenseCreate(**_expense_kwargs(start_year=year))


@pytest.mark.parametrize("rate", [-0.6, 0.51, float("inf"), float("nan")])
def test_expense_rejects_bad_escalation_rate(rate: float) -> None:
    with pytest.raises(ValidationError):
        ExpenseCreate(**_expense_kwargs(escalation_rate=rate))


def test_expense_update_rejects_bad_start_year() -> None:
    with pytest.raises(ValidationError):
        ExpenseUpdate(start_year=9999)


# ---------- Goal (target_year) ----------


@pytest.mark.parametrize("year", [1899, 2201])
def test_goal_rejects_out_of_range_target_year(year: int) -> None:
    with pytest.raises(ValidationError):
        GoalCreate(
            kind="retirement",
            name="Retire",
            target_amount=1_000_000,
            target_year=year,
        )


def test_goal_update_rejects_out_of_range_target_year() -> None:
    with pytest.raises(ValidationError):
        GoalUpdate(target_year=3000)


# ---------- Person.dob (V8) ----------


def test_person_rejects_future_dob() -> None:
    future = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        PersonCreate(name="P", dob=future)


def test_person_rejects_dob_too_far_in_past() -> None:
    ancient = date.today() - timedelta(days=121 * 366)
    with pytest.raises(ValidationError):
        PersonCreate(name="P", dob=ancient)


def test_person_accepts_normal_dob() -> None:
    dob = date(1985, 6, 1)
    p = PersonCreate(name="Alice", dob=dob)
    assert p.dob == dob


def test_person_update_rejects_future_dob() -> None:
    future = date.today() + timedelta(days=10)
    with pytest.raises(ValidationError):
        PersonUpdate(dob=future)


def test_person_update_allows_none_dob() -> None:
    # Update payload omitting dob entirely must remain valid.
    u = PersonUpdate(name="Renamed")
    assert u.dob is None


# ---------- NaN / inf guards (V7 cross-cut) ----------


@pytest.mark.parametrize(
    "field, value",
    [
        ("gross_amount", float("nan")),
        ("gross_amount", float("inf")),
        ("gross_amount", -1.0),
    ],
)
def test_income_rejects_bad_money(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        IncomeSourceCreate(**_income_kwargs(**{field: value}))
