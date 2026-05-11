from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Liability, Plan, User
from app.routers._helpers import get_or_404
from app.schemas.liability import LiabilityCreate, LiabilityRead, LiabilityUpdate

router = APIRouter(tags=["liabilities"])


def _amortised_monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """Standard fixed-rate mortgage payment. Falls back to straight-line if rate=0."""
    if annual_rate <= 0:
        return principal / term_months
    r = annual_rate / 12.0
    return principal * r / (1.0 - (1.0 + r) ** -term_months)


@router.get("/plans/{plan_id}/liabilities", response_model=list[LiabilityRead])
def list_liabilities(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Liability]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    return list(
        db.execute(
            select(Liability).where(Liability.plan_id == plan_id).order_by(Liability.id)
        ).scalars()
    )


@router.post(
    "/plans/{plan_id}/liabilities",
    response_model=LiabilityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_liability(
    plan_id: int,
    payload: LiabilityCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Liability:
    require_plan_access(plan_id, user, db, min_role="editor")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    data = payload.model_dump()
    if data.get("monthly_payment") in (None, 0):
        data["monthly_payment"] = _amortised_monthly_payment(
            data["principal"], data["interest_rate"], data["term_months"]
        )
    liability = Liability(plan_id=plan_id, **data)
    db.add(liability)
    db.commit()
    db.refresh(liability)
    return liability


@router.patch("/liabilities/{liability_id}", response_model=LiabilityRead)
def update_liability(
    liability_id: int,
    payload: LiabilityUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Liability:
    liability = get_or_404(Liability, liability_id, db)
    require_plan_access(liability.plan_id, user, db, min_role="editor")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(liability, k, v)
    db.commit()
    db.refresh(liability)
    return liability


@router.delete("/liabilities/{liability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_liability(
    liability_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    liability = get_or_404(Liability, liability_id, db)
    require_plan_access(liability.plan_id, user, db, min_role="editor")
    db.delete(liability)
    db.commit()
