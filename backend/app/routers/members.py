"""Membership management for shared plans.

- Anyone with viewer+ access can list the membership of a plan.
- Only owners can change roles or remove other members.
- Any member can remove themselves (self-leave), with one exception: the last
  remaining owner cannot leave (would orphan the plan).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import PlanMember, User
from app.schemas.sharing import MemberRead, MemberRoleUpdate

router = APIRouter(tags=["members"])


def _members_query(plan_id: int):
    return (
        select(PlanMember, User)
        .join(User, User.id == PlanMember.user_id)
        .where(PlanMember.plan_id == plan_id)
        .order_by(PlanMember.created_at)
    )


def _count_owners(db: Session, plan_id: int) -> int:
    return db.execute(
        select(func.count())
        .select_from(PlanMember)
        .where(PlanMember.plan_id == plan_id, PlanMember.role == "owner")
    ).scalar_one()


@router.get("/plans/{plan_id}/members", response_model=list[MemberRead])
def list_members(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MemberRead]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    rows = db.execute(_members_query(plan_id)).all()
    return [
        MemberRead(
            user_id=u.id,
            role=m.role,
            email=u.email,
            display_name=u.display_name,
            created_at=m.created_at,
        )
        for (m, u) in rows
    ]


@router.patch("/plans/{plan_id}/members/{user_id}", response_model=MemberRead)
def update_member_role(
    plan_id: int,
    user_id: int,
    payload: MemberRoleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberRead:
    require_plan_access(plan_id, user, db, min_role="owner")
    member = db.execute(
        select(PlanMember).where(
            PlanMember.plan_id == plan_id, PlanMember.user_id == user_id
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent demoting the last owner.
    if member.role == "owner" and payload.role != "owner":
        if _count_owners(db, plan_id) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot demote the last remaining owner of this plan",
            )
    member.role = payload.role
    db.commit()
    db.refresh(member)
    target = db.get(User, user_id)
    assert target is not None
    return MemberRead(
        user_id=target.id,
        role=member.role,
        email=target.email,
        display_name=target.display_name,
        created_at=member.created_at,
    )


@router.delete("/plans/{plan_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    plan_id: int,
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove a member from a plan. Self-leave is allowed for any role; removing
    someone else requires owner. The last owner cannot be removed.
    """
    is_self = user.id == user_id
    if not is_self:
        require_plan_access(plan_id, user, db, min_role="owner")
    else:
        require_plan_access(plan_id, user, db, min_role="viewer")

    member = db.execute(
        select(PlanMember).where(
            PlanMember.plan_id == plan_id, PlanMember.user_id == user_id
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == "owner" and _count_owners(db, plan_id) <= 1:
        raise HTTPException(
            status_code=409,
            detail="Cannot remove the last remaining owner of this plan",
        )

    db.delete(member)
    db.commit()
