from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Child, Plan, User
from app.routers._helpers import get_or_404
from app.schemas.child import ChildCreate, ChildRead, ChildUpdate

router = APIRouter(tags=["children"])


@router.get("/plans/{plan_id}/children", response_model=list[ChildRead])
def list_children(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Child]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    return list(
        db.execute(select(Child).where(Child.plan_id == plan_id).order_by(Child.id)).scalars()
    )


@router.post(
    "/plans/{plan_id}/children",
    response_model=ChildRead,
    status_code=status.HTTP_201_CREATED,
)
def create_child(
    plan_id: int,
    payload: ChildCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Child:
    require_plan_access(plan_id, user, db, min_role="editor")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    child = Child(plan_id=plan_id, **payload.model_dump())
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


@router.patch("/children/{child_id}", response_model=ChildRead)
def update_child(
    child_id: int,
    payload: ChildUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Child:
    child = get_or_404(Child, child_id, db)
    require_plan_access(child.plan_id, user, db, min_role="editor")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(child, k, v)
    db.commit()
    db.refresh(child)
    return child


@router.delete("/children/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child(
    child_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    child = get_or_404(Child, child_id, db)
    require_plan_access(child.plan_id, user, db, min_role="editor")
    db.delete(child)
    db.commit()
