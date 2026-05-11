from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Expense, Plan, User
from app.routers._helpers import get_or_404
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseUpdate

router = APIRouter(tags=["expenses"])


@router.get("/plans/{plan_id}/expenses", response_model=list[ExpenseRead])
def list_expenses(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Expense]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    return list(
        db.execute(select(Expense).where(Expense.plan_id == plan_id).order_by(Expense.id)).scalars()
    )


@router.post(
    "/plans/{plan_id}/expenses",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    plan_id: int,
    payload: ExpenseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Expense:
    require_plan_access(plan_id, user, db, min_role="editor")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    e = Expense(plan_id=plan_id, **payload.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.patch("/expenses/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Expense:
    e = get_or_404(Expense, expense_id, db)
    require_plan_access(e.plan_id, user, db, min_role="editor")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    db.commit()
    db.refresh(e)
    return e


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    e = get_or_404(Expense, expense_id, db)
    require_plan_access(e.plan_id, user, db, min_role="editor")
    db.delete(e)
    db.commit()
