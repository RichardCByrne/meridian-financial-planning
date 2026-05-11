from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Plan, Scenario, User
from app.routers._helpers import get_or_404
from app.schemas.scenario import ScenarioCreate, ScenarioRead, ScenarioUpdate

router = APIRouter(tags=["scenarios"])


@router.get("/plans/{plan_id}/scenarios", response_model=list[ScenarioRead])
def list_scenarios(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ScenarioRead]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    rows = list(
        db.execute(
            select(Scenario).where(Scenario.plan_id == plan_id).order_by(Scenario.id)
        ).scalars()
    )
    return [ScenarioRead.from_orm_row(r) for r in rows]


@router.post(
    "/plans/{plan_id}/scenarios",
    response_model=ScenarioRead,
    status_code=status.HTTP_201_CREATED,
)
def create_scenario(
    plan_id: int,
    payload: ScenarioCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioRead:
    require_plan_access(plan_id, user, db, min_role="editor")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    s = Scenario(
        plan_id=plan_id,
        name=payload.name,
        parent_scenario_id=payload.parent_scenario_id,
        overrides_json=payload.overrides,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return ScenarioRead.from_orm_row(s)


@router.patch("/scenarios/{scenario_id}", response_model=ScenarioRead)
def update_scenario(
    scenario_id: int,
    payload: ScenarioUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioRead:
    s = get_or_404(Scenario, scenario_id, db)
    require_plan_access(s.plan_id, user, db, min_role="editor")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        s.name = data["name"]
    if "parent_scenario_id" in data:
        s.parent_scenario_id = data["parent_scenario_id"]
    if "overrides" in data and data["overrides"] is not None:
        s.overrides_json = data["overrides"]
    db.commit()
    db.refresh(s)
    return ScenarioRead.from_orm_row(s)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    s = get_or_404(Scenario, scenario_id, db)
    require_plan_access(s.plan_id, user, db, min_role="editor")
    db.delete(s)
    db.commit()
