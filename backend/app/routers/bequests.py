from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Bequest, Person, User
from app.routers._helpers import get_or_404
from app.schemas.bequest import BequestCreate, BequestRead, BequestUpdate

router = APIRouter(tags=["bequests"])


def _validate_person_in_plan(person_id: int, plan_id: int, db: Session) -> None:
    p = db.get(Person, person_id)
    if p is None or p.plan_id != plan_id:
        raise HTTPException(status_code=422, detail=f"Person {person_id} not found in this plan")


@router.get("/plans/{plan_id}/bequests", response_model=list[BequestRead])
def list_bequests(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BequestRead]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    rows = list(db.execute(select(Bequest).where(Bequest.plan_id == plan_id)).scalars())
    return [BequestRead.model_validate(r) for r in rows]


@router.post("/plans/{plan_id}/bequests", response_model=BequestRead, status_code=201)
def create_bequest(
    plan_id: int,
    body: BequestCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BequestRead:
    require_plan_access(plan_id, user, db, min_role="editor")
    _validate_person_in_plan(body.from_person_id, plan_id, db)
    if body.to_person_id is not None:
        _validate_person_in_plan(body.to_person_id, plan_id, db)
    row = Bequest(plan_id=plan_id, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return BequestRead.model_validate(row)


@router.patch("/bequests/{bequest_id}", response_model=BequestRead)
def update_bequest(
    bequest_id: int,
    body: BequestUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BequestRead:
    row = get_or_404(Bequest, bequest_id, db)
    require_plan_access(row.plan_id, user, db, min_role="editor")
    if body.to_person_id is not None:
        _validate_person_in_plan(body.to_person_id, row.plan_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return BequestRead.model_validate(row)


@router.delete("/bequests/{bequest_id}", status_code=204)
def delete_bequest(
    bequest_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    row = get_or_404(Bequest, bequest_id, db)
    require_plan_access(row.plan_id, user, db, min_role="editor")
    db.delete(row)
    db.commit()
