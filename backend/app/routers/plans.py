from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user, grant_plan_membership, require_plan_access
from app.db import get_db
from app.models import Assumptions, Liability, Person, Plan, PlanMember, User
from app.routers._helpers import get_or_404
from app.schemas.plan import PlanCreate, PlanRead, PlanUpdate
from app.services.serialisation import hydrate_plan, serialise_plan

router = APIRouter(prefix="/plans", tags=["plans"])


def _load_plan_with_children(plan_id: int, db: Session) -> Plan:
    plan = db.execute(
        select(Plan)
        .where(Plan.id == plan_id)
        .options(
            selectinload(Plan.people).selectinload(Person.income_sources),
            selectinload(Plan.expenses),
            selectinload(Plan.assets),
            selectinload(Plan.liabilities).selectinload(Liability.adjustments),
            selectinload(Plan.goals),
            selectinload(Plan.scenarios),
            selectinload(Plan.bequests),
            selectinload(Plan.benefits),
            selectinload(Plan.children),
            selectinload(Plan.assumptions),
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get("", response_model=list[PlanRead])
def list_plans(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Plan]:
    """List plans the caller is a member of (any role)."""
    return list(
        db.execute(
            select(Plan)
            .join(PlanMember, PlanMember.plan_id == Plan.id)
            .where(PlanMember.user_id == user.id)
            .order_by(Plan.created_at.desc())
        ).scalars()
    )


@router.post("", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Plan:
    plan = Plan(**payload.model_dump())
    db.add(plan)
    db.flush()
    db.add(Assumptions(plan_id=plan.id))
    grant_plan_membership(db, plan.id, user.id, role="owner")
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/{plan_id}", response_model=PlanRead)
def get_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Plan:
    require_plan_access(plan_id, user, db, min_role="viewer")
    return get_or_404(Plan, plan_id, db)


@router.patch("/{plan_id}", response_model=PlanRead)
def update_plan(
    plan_id: int,
    payload: PlanUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Plan:
    require_plan_access(plan_id, user, db, min_role="editor")
    plan = get_or_404(Plan, plan_id, db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    require_plan_access(plan_id, user, db, min_role="owner")
    plan = get_or_404(Plan, plan_id, db)
    db.delete(plan)
    db.commit()


@router.post("/{plan_id}/clone", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
def clone_plan(
    plan_id: int,
    payload: dict[str, Any] | None = Body(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Plan:
    """Deep-copy a plan and all of its children under a new name. The cloner becomes owner."""
    require_plan_access(plan_id, user, db, min_role="viewer")
    src = _load_plan_with_children(plan_id, db)
    new_name = (payload or {}).get("name") or f"{src.name} (copy)"
    snapshot = serialise_plan(src)
    new_plan = hydrate_plan(snapshot, db, name_override=new_name)
    grant_plan_membership(db, new_plan.id, user.id, role="owner")
    db.commit()
    return new_plan


@router.get("/{plan_id}/export")
def export_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    plan = _load_plan_with_children(plan_id, db)
    return serialise_plan(plan)


@router.post("/import", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
def import_plan(
    payload: dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Plan:
    """Create a plan from a previously-exported JSON snapshot. Importer becomes owner."""
    try:
        plan = hydrate_plan(payload, db)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid plan payload: {e}") from e
    grant_plan_membership(db, plan.id, user.id, role="owner")
    db.commit()
    return plan
