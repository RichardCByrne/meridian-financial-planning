"""Shared helpers for router CRUD + authz tests.

Not a test module itself (leading underscore keeps pytest from collecting it).
Provides multi-user identity switching so the editor/viewer/non-member guards
on the CRUD routers can be exercised. Happy-path tests can rely on the default
dev-auth user instead.
"""

from contextlib import contextmanager

from app.auth import get_current_user
from app.db import SessionLocal
from app.main import app
from app.models import User


def ensure_user(firebase_uid: str, email: str) -> User:
    with SessionLocal() as db:
        existing = db.query(User).filter(User.firebase_uid == firebase_uid).one_or_none()
        if existing is not None:
            return existing
        u = User(firebase_uid=firebase_uid, email=email, display_name=email)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u


@contextmanager
def as_user(firebase_uid: str, email: str):
    user = ensure_user(firebase_uid, email)

    def _override():
        with SessionLocal() as db:
            return db.query(User).filter(User.id == user.id).one()

    app.dependency_overrides[get_current_user] = _override
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_user, None)
