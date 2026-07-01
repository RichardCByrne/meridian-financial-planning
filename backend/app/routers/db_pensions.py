from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import DBPension, Person, User
from app.routers._helpers import get_or_404
from app.schemas.db_pension import DBPensionCreate, DBPensionRead, DBPensionUpdate

router = APIRouter(tags=["db_pensions"])


def _validate_person_in_plan(person_id: int, plan_id: int, db: Session) -> None:
    p = db.get(Person, person_id)
    if p is None or p.plan_id != plan_id:
        raise HTTPException(status_code=422, detail=f"Person {person_id} not found in this plan")


@router.get("/plans/{plan_id}/db-pensions", response_model=list[DBPensionRead])
def list_db_pensions(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DBPensionRead]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    rows = list(db.execute(select(DBPension).where(DBPension.plan_id == plan_id)).scalars())
    return [DBPensionRead.model_validate(r) for r in rows]


@router.post("/plans/{plan_id}/db-pensions", response_model=DBPensionRead, status_code=201)
def create_db_pension(
    plan_id: int,
    body: DBPensionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DBPensionRead:
    require_plan_access(plan_id, user, db, min_role="editor")
    _validate_person_in_plan(body.person_id, plan_id, db)
    row = DBPension(plan_id=plan_id, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return DBPensionRead.model_validate(row)


@router.patch("/db-pensions/{pension_id}", response_model=DBPensionRead)
def update_db_pension(
    pension_id: int,
    body: DBPensionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DBPensionRead:
    row = get_or_404(DBPension, pension_id, db)
    require_plan_access(row.plan_id, user, db, min_role="editor")
    if body.person_id is not None:
        _validate_person_in_plan(body.person_id, row.plan_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return DBPensionRead.model_validate(row)


@router.delete("/db-pensions/{pension_id}", status_code=204)
def delete_db_pension(
    pension_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    row = get_or_404(DBPension, pension_id, db)
    require_plan_access(row.plan_id, user, db, min_role="editor")
    db.delete(row)
    db.commit()
