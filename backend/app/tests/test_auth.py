"""Auth: multi-user plan isolation + role enforcement.

We override `get_current_user` per request so we can simulate two distinct users
without going through Firebase. Same trick the production code paths will use
once a real Firebase token lands in the Authorization header.
"""

from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.auth import get_current_user, grant_plan_membership
from app.db import SessionLocal
from app.main import app
from app.models import User


def _ensure_user(firebase_uid: str, email: str) -> User:
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
def _as_user(firebase_uid: str, email: str):
    """Temporarily route get_current_user to a specific user inside a TestClient."""
    user = _ensure_user(firebase_uid, email)

    def _override():
        # Re-fetch in the request's session so SQLAlchemy doesn't complain.
        from app.db import SessionLocal as _SL

        with _SL() as db:
            return db.query(User).filter(User.id == user.id).one()

    app.dependency_overrides[get_current_user] = _override
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _seed_plan_for(user: User, name: str = "Plan A") -> int:
    with TestClient(app) as client:
        with _as_user(user.firebase_uid, user.email or ""):
            r = client.post(
                "/api/plans", json={"name": name, "base_year": 2026, "projection_years": 5}
            )
            assert r.status_code == 201
            return r.json()["id"]


def test_user_cannot_see_other_users_plan():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Alice's plan")

    with TestClient(app) as client:
        with _as_user(bob.firebase_uid, bob.email or ""):
            # List doesn't show Alice's plan to Bob.
            listed = client.get("/api/plans").json()
            assert all(p["id"] != plan_id for p in listed)
            # Direct GET returns 404 (deliberate — don't leak existence).
            assert client.get(f"/api/plans/{plan_id}").status_code == 404
            # Mutations are also 404 (since Bob has no membership row).
            assert client.delete(f"/api/plans/{plan_id}").status_code == 404


def test_creator_becomes_owner_automatically():
    alice = _ensure_user("alice-uid", "alice@example.com")
    plan_id = _seed_plan_for(alice, "Alice owner test")

    from app.auth import get_member_role

    with SessionLocal() as db:
        role = get_member_role(db, plan_id, alice.id)
        assert role == "owner"


def test_shared_plan_grants_access_per_role():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Shared plan")

    # Alice grants Bob 'viewer'.
    with SessionLocal() as db:
        grant_plan_membership(db, plan_id, bob.id, role="viewer")

    with TestClient(app) as client:
        with _as_user(bob.firebase_uid, bob.email or ""):
            # Viewer can read.
            assert client.get(f"/api/plans/{plan_id}").status_code == 200
            assert client.get(f"/api/plans/{plan_id}/people").status_code == 200
            # Viewer cannot mutate.
            r = client.post(
                f"/api/plans/{plan_id}/people",
                json={"name": "Bob's attempt", "dob": "1990-01-01", "is_primary": False},
            )
            assert r.status_code == 403
            assert "viewer" in r.json()["detail"].lower() or "editor" in r.json()["detail"].lower()
            # Viewer cannot delete the plan.
            assert client.delete(f"/api/plans/{plan_id}").status_code == 403


def test_editor_can_mutate_but_not_delete_plan():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Editor test")

    with SessionLocal() as db:
        grant_plan_membership(db, plan_id, bob.id, role="editor")

    with TestClient(app) as client:
        with _as_user(bob.firebase_uid, bob.email or ""):
            # Editor can add a person.
            r = client.post(
                f"/api/plans/{plan_id}/people",
                json={"name": "Editor add", "dob": "1985-01-01", "is_primary": True},
            )
            assert r.status_code == 201
            # Editor cannot delete the plan (owner-only).
            assert client.delete(f"/api/plans/{plan_id}").status_code == 403


def test_clone_makes_caller_the_owner_of_the_copy():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Clonable")

    with SessionLocal() as db:
        grant_plan_membership(db, plan_id, bob.id, role="viewer")

    with TestClient(app) as client:
        with _as_user(bob.firebase_uid, bob.email or ""):
            r = client.post(f"/api/plans/{plan_id}/clone", json={"name": "Bob's copy"})
            assert r.status_code == 201
            new_id = r.json()["id"]

    from app.auth import get_member_role

    with SessionLocal() as db:
        # Bob owns the copy.
        assert get_member_role(db, new_id, bob.id) == "owner"
        # Alice has no membership on the copy.
        assert get_member_role(db, new_id, alice.id) is None


def test_unauthenticated_request_is_rejected_in_production_mode(monkeypatch):
    """When MERIDIAN_DEV_AUTH=false, missing token returns 401."""
    monkeypatch.setattr("app.auth.DEV_AUTH", False)
    with TestClient(app) as client:
        r = client.get("/api/plans")
        assert r.status_code == 401
        assert "bearer" in r.json()["detail"].lower()
