from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Goal, Plan, User
from app.routers._helpers import get_or_404
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate

router = APIRouter(tags=["goals"])


def _validate_target_year(plan: Plan, target_year: int | None) -> None:
    if target_year is None:
        return
    last_year = plan.base_year + plan.projection_years - 1
    if target_year < plan.base_year or target_year > last_year:
        raise HTTPException(
            status_code=400,
            detail=(
                f"target_year {target_year} is outside the plan horizon "
                f"({plan.base_year}–{last_year})"
            ),
        )


@router.get("/plans/{plan_id}/goals", response_model=list[GoalRead])
def list_goals(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Goal]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    return list(
        db.execute(
            select(Goal).where(Goal.plan_id == plan_id).order_by(Goal.target_year, Goal.id)
        ).scalars()
    )


@router.post(
    "/plans/{plan_id}/goals",
    response_model=GoalRead,
    status_code=status.HTTP_201_CREATED,
)
def create_goal(
    plan_id: int,
    payload: GoalCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    require_plan_access(plan_id, user, db, min_role="editor")
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    _validate_target_year(plan, payload.target_year)
    g = Goal(plan_id=plan_id, **payload.model_dump())
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@router.patch("/goals/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    g = get_or_404(Goal, goal_id, db)
    require_plan_access(g.plan_id, user, db, min_role="editor")
    data = payload.model_dump(exclude_unset=True)
    if "target_year" in data and data["target_year"] is not None:
        _validate_target_year(g.plan, data["target_year"])
    for k, v in data.items():
        setattr(g, k, v)
    db.commit()
    db.refresh(g)
    return g


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    g = get_or_404(Goal, goal_id, db)
    require_plan_access(g.plan_id, user, db, min_role="editor")
    db.delete(g)
    db.commit()
