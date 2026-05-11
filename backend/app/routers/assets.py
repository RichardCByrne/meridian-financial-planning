from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Asset, Plan, User
from app.routers._helpers import get_or_404
from app.schemas.asset import AssetCreate, AssetRead, AssetUpdate

router = APIRouter(tags=["assets"])


@router.get("/plans/{plan_id}/assets", response_model=list[AssetRead])
def list_assets(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Asset]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    return list(
        db.execute(select(Asset).where(Asset.plan_id == plan_id).order_by(Asset.id)).scalars()
    )


@router.post(
    "/plans/{plan_id}/assets",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_asset(
    plan_id: int,
    payload: AssetCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Asset:
    require_plan_access(plan_id, user, db, min_role="editor")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    a = Asset(plan_id=plan_id, **payload.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.patch("/assets/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: int,
    payload: AssetUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Asset:
    a = get_or_404(Asset, asset_id, db)
    require_plan_access(a.plan_id, user, db, min_role="editor")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    a = get_or_404(Asset, asset_id, db)
    require_plan_access(a.plan_id, user, db, min_role="editor")
    db.delete(a)
    db.commit()
