"""Plan-sharing invites.

Two-step share-link flow: an owner generates an invite (POST /plans/{id}/invites)
which returns a unique token. Anyone signed in who knows the token can accept
(POST /invites/{token}/accept), which adds them as a PlanMember at the encoded
role and consumes the invite. Optionally an invite can be email-bound, in which
case only a user whose Firebase identity matches that email may accept.

The preview endpoint (GET /invites/{token}) intentionally does NOT require
auth, so a recipient can read what they're being invited to before signing in.
"""

from datetime import timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, grant_plan_membership, require_plan_access
from app.db import get_db, utcnow
from app.models import Plan, PlanInvite, User
from app.schemas.sharing import InviteCreate, InvitePreview, InviteRead

router = APIRouter(tags=["invites"])

_TOKEN_BYTES = 24  # → 32-char URL-safe string


def _invite_or_404(token: str, db: Session) -> PlanInvite:
    inv = db.execute(
        select(PlanInvite).where(PlanInvite.token == token)
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    return inv


@router.post(
    "/plans/{plan_id}/invites",
    response_model=InviteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invite(
    plan_id: int,
    payload: InviteCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanInvite:
    require_plan_access(plan_id, user, db, min_role="owner")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    expires_at = (
        utcnow() + timedelta(days=payload.expires_days)
        if payload.expires_days
        else None
    )
    inv = PlanInvite(
        plan_id=plan_id,
        created_by_user_id=user.id,
        role=payload.role,
        email=str(payload.email).lower() if payload.email else None,
        token=token_urlsafe(_TOKEN_BYTES),
        expires_at=expires_at,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.get("/plans/{plan_id}/invites", response_model=list[InviteRead])
def list_invites(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PlanInvite]:
    """List pending (unaccepted) invites. Owner-only."""
    require_plan_access(plan_id, user, db, min_role="owner")
    return list(
        db.execute(
            select(PlanInvite)
            .where(PlanInvite.plan_id == plan_id, PlanInvite.accepted_at.is_(None))
            .order_by(PlanInvite.created_at.desc())
        ).scalars()
    )


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(
    invite_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    inv = db.get(PlanInvite, invite_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    require_plan_access(inv.plan_id, user, db, min_role="owner")
    db.delete(inv)
    db.commit()


@router.get("/invites/{token}", response_model=InvitePreview)
def preview_invite(token: str, db: Session = Depends(get_db)) -> InvitePreview:
    """Public preview. No auth — recipient might not be signed in yet.

    Returns 410 if already accepted, 410 if expired, 404 if unknown.
    """
    inv = _invite_or_404(token, db)
    if inv.accepted_at is not None:
        raise HTTPException(status_code=410, detail="Invite already accepted")
    if inv.expires_at is not None and inv.expires_at < utcnow():
        raise HTTPException(status_code=410, detail="Invite expired")
    plan = db.get(Plan, inv.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no longer exists")
    inviter = db.get(User, inv.created_by_user_id) if inv.created_by_user_id else None
    return InvitePreview(
        plan_id=plan.id,
        plan_name=plan.name,
        role=inv.role,
        email_bound=inv.email is not None,
        inviter_display_name=inviter.display_name if inviter else None,
        expires_at=inv.expires_at,
    )


@router.post("/invites/{token}/accept", response_model=InviteRead)
def accept_invite(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanInvite:
    inv = _invite_or_404(token, db)
    if inv.accepted_at is not None:
        raise HTTPException(status_code=410, detail="Invite already accepted")
    if inv.expires_at is not None and inv.expires_at < utcnow():
        raise HTTPException(status_code=410, detail="Invite expired")
    if inv.email is not None:
        if (user.email or "").lower() != inv.email.lower():
            raise HTTPException(
                status_code=403,
                detail="This invite is bound to a different email address",
            )

    grant_plan_membership(db, inv.plan_id, user.id, role=inv.role)
    inv.accepted_by_user_id = user.id
    inv.accepted_at = utcnow()
    db.commit()
    db.refresh(inv)
    return inv
