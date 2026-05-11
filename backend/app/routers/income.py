from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import IncomeSource, Person, User
from app.routers._helpers import get_or_404
from app.schemas.income import IncomeSourceCreate, IncomeSourceRead, IncomeSourceUpdate

router = APIRouter(tags=["income"])


@router.get("/people/{person_id}/income", response_model=list[IncomeSourceRead])
def list_income(
    person_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IncomeSource]:
    person = get_or_404(Person, person_id, db)
    require_plan_access(person.plan_id, user, db, min_role="viewer")
    return list(
        db.execute(
            select(IncomeSource).where(IncomeSource.person_id == person_id).order_by(IncomeSource.id)
        ).scalars()
    )


@router.post(
    "/people/{person_id}/income",
    response_model=IncomeSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_income(
    person_id: int,
    payload: IncomeSourceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncomeSource:
    person = get_or_404(Person, person_id, db)
    require_plan_access(person.plan_id, user, db, min_role="editor")
    inc = IncomeSource(person_id=person_id, **payload.model_dump())
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


@router.patch("/income/{income_id}", response_model=IncomeSourceRead)
def update_income(
    income_id: int,
    payload: IncomeSourceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncomeSource:
    inc = get_or_404(IncomeSource, income_id, db, name="Income source")
    require_plan_access(inc.person.plan_id, user, db, min_role="editor")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(inc, k, v)
    db.commit()
    db.refresh(inc)
    return inc


@router.delete("/income/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(
    income_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    inc = get_or_404(IncomeSource, income_id, db, name="Income source")
    require_plan_access(inc.person.plan_id, user, db, min_role="editor")
    db.delete(inc)
    db.commit()
