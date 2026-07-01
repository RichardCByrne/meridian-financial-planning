"""Authentication and authorisation.

Identity is owned by Firebase Auth: the frontend obtains an ID token via the
Firebase JS SDK, sends it as `Authorization: Bearer <token>`, and we verify
it with the Firebase Admin SDK. We persist a thin `User` row keyed by the
Firebase UID so the rest of the schema can foreign-key into it.

Two operating modes:

- **Production** (`MERIDIAN_DEV_AUTH != "true"`): firebase-admin must be
  initialised via `FIREBASE_SERVICE_ACCOUNT_PATH` (path to a service-account
  JSON). Tokens are verified on every request.

- **Local dev** (`MERIDIAN_DEV_AUTH == "true"`, the default): token verification
  is skipped. Every request resolves to a single seeded "dev-local" user so the
  existing `dev.ps1` workflow keeps working without a Firebase project.

Authorisation is by `PlanMember` rows. `require_plan_access` looks up the
caller's role for a given plan and 403s (or 404s, to avoid leaking existence)
if the role is missing or insufficient.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PLAN_ROLES, Plan, PlanMember, User

logger = logging.getLogger(__name__)

DEV_AUTH = os.environ.get("MERIDIAN_DEV_AUTH", "true").lower() == "true"
DEV_USER_FIREBASE_UID = "dev-local"
DEV_USER_EMAIL = "dev@meridian.local"
DEV_USER_DISPLAY_NAME = "Local Dev User"

_firebase_initialised = False


def _ensure_firebase_initialised() -> None:
    """Lazy-init firebase-admin on first real verification call."""
    global _firebase_initialised
    if _firebase_initialised or DEV_AUTH:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError as e:
        raise RuntimeError(
            "firebase-admin not installed but MERIDIAN_DEV_AUTH is not 'true'. "
            "Install with `pip install -e \".[dev]\"` or set MERIDIAN_DEV_AUTH=true."
        ) from e

    cred_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
    if not cred_path:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT_PATH env var required when MERIDIAN_DEV_AUTH != true"
        )
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    _firebase_initialised = True


def _find_or_create_user(
    db: Session,
    firebase_uid: str,
    email: str | None = None,
    display_name: str | None = None,
) -> User:
    user = db.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
    if user is not None:
        # Refresh email / display name if Firebase has newer values. Only commit
        # when something actually changed — otherwise every authenticated
        # request would issue a needless write (adds latency and cost on the
        # Neon serverless tier).
        changed = False
        if email and user.email != email:
            user.email = email
            changed = True
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            changed = True
        if changed:
            db.commit()
        return user
    user = User(firebase_uid=firebase_uid, email=email, display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _email_is_verified(decoded: dict) -> bool:
    """True unless the token carries an email that Firebase reports unverified.

    Tokens with no `email` claim (e.g. phone auth) are treated as verified —
    the email-based attack this guards against doesn't apply to them.
    """
    if not decoded.get("email"):
        return True
    return bool(decoded.get("email_verified", False))


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: resolve the calling user from the bearer token.

    Returns the persisted `User` row. Raises 401 on missing / invalid token
    (unless dev-mode is on, in which case the seeded dev user is returned).
    """
    if DEV_AUTH:
        return _find_or_create_user(
            db,
            firebase_uid=DEV_USER_FIREBASE_UID,
            email=DEV_USER_EMAIL,
            display_name=DEV_USER_DISPLAY_NAME,
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = authorization.split(" ", 1)[1].strip()

    _ensure_firebase_initialised()
    try:
        from firebase_admin import auth as fb_auth

        decoded = fb_auth.verify_id_token(token)
    except Exception as e:  # noqa: BLE001
        logger.info("Token verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from e

    # Reject accounts whose email is not yet verified. Email/password sign-ups
    # start unverified; without this an attacker could register with a victim's
    # address and, e.g., accept an email-bound plan invite meant for them.
    # Federated providers (Google) come back already verified, so this only
    # gates the password provider. Tokens without an email claim are unaffected.
    if not _email_is_verified(decoded):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before continuing.",
        )

    return _find_or_create_user(
        db,
        firebase_uid=decoded["uid"],
        email=decoded.get("email"),
        display_name=decoded.get("name"),
    )


def _role_meets(actual: str | None, minimum: str) -> bool:
    if actual is None:
        return False
    if actual not in PLAN_ROLES or minimum not in PLAN_ROLES:
        return False
    return PLAN_ROLES.index(actual) >= PLAN_ROLES.index(minimum)


def get_member_role(db: Session, plan_id: int, user_id: int) -> str | None:
    return db.execute(
        select(PlanMember.role).where(
            PlanMember.plan_id == plan_id, PlanMember.user_id == user_id
        )
    ).scalar_one_or_none()


def require_plan_access(
    plan_id: int,
    user: User,
    db: Session,
    *,
    min_role: str = "viewer",
) -> str:
    """Verify `user` has at least `min_role` on `plan_id`. Returns the actual role.

    Raises 404 (not 403) when the user has no membership at all, to avoid
    leaking the existence of plans they can't see.
    """
    role = get_member_role(db, plan_id, user.id)
    if role is None:
        # 404 deliberately — don't tell unauthenticated users which plan ids exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    if not _role_meets(role, min_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires at least '{min_role}' role; you have '{role}'.",
        )
    return role


def require_role(min_role: str) -> Callable[[int, User, Session], str]:
    """FastAPI dep factory. Use as `Depends(require_role('editor'))` together with
    a `plan_id` path parameter and `Depends(get_current_user)` already in scope.

    Routes that don't have a plan_id directly call require_plan_access manually
    after looking up the parent (e.g. PATCH /people/{id} → person.plan_id).
    """
    def _dep(
        plan_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> str:
        return require_plan_access(plan_id, user, db, min_role=min_role)

    return _dep


def grant_plan_membership(db: Session, plan_id: int, user_id: int, role: str) -> PlanMember:
    """Idempotent: returns existing membership or creates one with the given role."""
    existing = db.execute(
        select(PlanMember).where(
            PlanMember.plan_id == plan_id, PlanMember.user_id == user_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    member = PlanMember(plan_id=plan_id, user_id=user_id, role=role)
    db.add(member)
    db.commit()
    return member


def assign_orphan_plans_to_dev_user(db: Session) -> int:
    """Lightweight migration: any plan without members gets the dev user as owner.

    Only runs when MERIDIAN_DEV_AUTH is on — in production an orphan plan is a
    real problem and should be flagged manually rather than silently re-owned.
    Returns the number of plans adopted.
    """
    if not DEV_AUTH:
        return 0
    dev_user = _find_or_create_user(
        db, DEV_USER_FIREBASE_UID, DEV_USER_EMAIL, DEV_USER_DISPLAY_NAME
    )
    orphans = list(
        db.execute(
            select(Plan).where(~Plan.members.any())
        ).scalars()
    )
    for plan in orphans:
        grant_plan_membership(db, plan.id, dev_user.id, role="owner")
    return len(orphans)
