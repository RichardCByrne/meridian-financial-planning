from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Benefit, Person, Plan, User
from app.routers._helpers import get_or_404
from app.schemas.benefit import BenefitCreate, BenefitRead, BenefitUpdate

router = APIRouter(tags=["benefits"])


def _check_person_in_plan(person_id: int, plan_id: int, db: Session) -> None:
    person = db.get(Person, person_id)
    if person is None or person.plan_id != plan_id:
        raise HTTPException(status_code=422, detail="person_id does not belong to this plan")


@router.get("/plans/{plan_id}/benefits", response_model=list[BenefitRead])
def list_benefits(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Benefit]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    return list(
        db.execute(
            select(Benefit).where(Benefit.plan_id == plan_id).order_by(Benefit.id)
        ).scalars()
    )


@router.post(
    "/plans/{plan_id}/benefits",
    response_model=BenefitRead,
    status_code=status.HTTP_201_CREATED,
)
def create_benefit(
    plan_id: int,
    payload: BenefitCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Benefit:
    require_plan_access(plan_id, user, db, min_role="editor")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    _check_person_in_plan(payload.person_id, plan_id, db)
    benefit = Benefit(plan_id=plan_id, **payload.model_dump())
    db.add(benefit)
    db.commit()
    db.refresh(benefit)
    return benefit


@router.patch("/benefits/{benefit_id}", response_model=BenefitRead)
def update_benefit(
    benefit_id: int,
    payload: BenefitUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Benefit:
    benefit = get_or_404(Benefit, benefit_id, db)
    require_plan_access(benefit.plan_id, user, db, min_role="editor")
    data = payload.model_dump(exclude_unset=True)
    if "person_id" in data and data["person_id"] is not None:
        _check_person_in_plan(data["person_id"], benefit.plan_id, db)
    for k, v in data.items():
        setattr(benefit, k, v)
    db.commit()
    db.refresh(benefit)
    return benefit


@router.delete("/benefits/{benefit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_benefit(
    benefit_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    benefit = get_or_404(Benefit, benefit_id, db)
    require_plan_access(benefit.plan_id, user, db, min_role="editor")
    db.delete(benefit)
    db.commit()
