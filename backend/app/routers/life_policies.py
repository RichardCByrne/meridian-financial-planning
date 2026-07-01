from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import LifePolicy, Person, User
from app.routers._helpers import get_or_404
from app.schemas.life_policy import LifePolicyCreate, LifePolicyRead, LifePolicyUpdate

router = APIRouter(tags=["life_policies"])


def _validate_person_in_plan(person_id: int, plan_id: int, db: Session) -> None:
    p = db.get(Person, person_id)
    if p is None or p.plan_id != plan_id:
        raise HTTPException(status_code=422, detail=f"Person {person_id} not found in this plan")


@router.get("/plans/{plan_id}/life-policies", response_model=list[LifePolicyRead])
def list_life_policies(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LifePolicyRead]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    rows = list(db.execute(select(LifePolicy).where(LifePolicy.plan_id == plan_id)).scalars())
    return [LifePolicyRead.model_validate(r) for r in rows]


@router.post("/plans/{plan_id}/life-policies", response_model=LifePolicyRead, status_code=201)
def create_life_policy(
    plan_id: int,
    body: LifePolicyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LifePolicyRead:
    require_plan_access(plan_id, user, db, min_role="editor")
    _validate_person_in_plan(body.person_id, plan_id, db)
    row = LifePolicy(plan_id=plan_id, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return LifePolicyRead.model_validate(row)


@router.patch("/life-policies/{policy_id}", response_model=LifePolicyRead)
def update_life_policy(
    policy_id: int,
    body: LifePolicyUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LifePolicyRead:
    row = get_or_404(LifePolicy, policy_id, db)
    require_plan_access(row.plan_id, user, db, min_role="editor")
    if body.person_id is not None:
        _validate_person_in_plan(body.person_id, row.plan_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return LifePolicyRead.model_validate(row)


@router.delete("/life-policies/{policy_id}", status_code=204)
def delete_life_policy(
    policy_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    row = get_or_404(LifePolicy, policy_id, db)
    require_plan_access(row.plan_id, user, db, min_role="editor")
    db.delete(row)
    db.commit()
