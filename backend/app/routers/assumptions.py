from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Assumptions, Plan, User
from app.schemas.assumptions import AssumptionsRead, AssumptionsUpsert

router = APIRouter(tags=["assumptions"])


@router.get("/plans/{plan_id}/assumptions", response_model=AssumptionsRead)
def get_assumptions(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Assumptions:
    require_plan_access(plan_id, user, db, min_role="viewer")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    a = db.execute(
        select(Assumptions).where(Assumptions.plan_id == plan_id)
    ).scalar_one_or_none()
    if a is None:
        a = Assumptions(plan_id=plan_id)
        db.add(a)
        db.commit()
        db.refresh(a)
    return a


@router.put("/plans/{plan_id}/assumptions", response_model=AssumptionsRead)
def upsert_assumptions(
    plan_id: int,
    payload: AssumptionsUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Assumptions:
    require_plan_access(plan_id, user, db, min_role="editor")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    a = db.execute(
        select(Assumptions).where(Assumptions.plan_id == plan_id)
    ).scalar_one_or_none()
    if a is None:
        a = Assumptions(plan_id=plan_id, **payload.model_dump())
        db.add(a)
    else:
        for k, v in payload.model_dump().items():
            setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a
