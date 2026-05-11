"""Phase 10 tests: invite + accept + role management round-trip."""

from contextlib import contextmanager
from datetime import timedelta

from app.db import utcnow
from secrets import token_urlsafe

from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.db import SessionLocal
from app.main import app
from app.models import PlanInvite, User


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
    user = _ensure_user(firebase_uid, email)

    def _override():
        with SessionLocal() as db:
            return db.query(User).filter(User.id == user.id).one()

    app.dependency_overrides[get_current_user] = _override
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _seed_plan_for(user: User, name: str = "Test plan") -> int:
    with TestClient(app) as client:
        with _as_user(user.firebase_uid, user.email or ""):
            r = client.post(
                "/api/plans",
                json={"name": name, "base_year": 2026, "projection_years": 5},
            )
            assert r.status_code == 201
            return r.json()["id"]


# ---------- invite create / preview / accept ----------


def test_owner_creates_invite_and_recipient_accepts():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Round-trip plan")

    with TestClient(app) as client:
        # Alice generates an editor invite.
        with _as_user(alice.firebase_uid, alice.email or ""):
            r = client.post(
                f"/api/plans/{plan_id}/invites",
                json={"role": "editor"},
            )
            assert r.status_code == 201
            token = r.json()["token"]
            assert r.json()["accepted_at"] is None

        # Anyone (no auth) can preview.
        # Note: TestClient still routes through the auth override; preview is open
        # by virtue of its dependencies, not because the override is removed.
        with _as_user(bob.firebase_uid, bob.email or ""):
            preview = client.get(f"/api/invites/{token}").json()
            assert preview["plan_name"] == "Round-trip plan"
            assert preview["role"] == "editor"
            assert preview["email_bound"] is False

            # Bob accepts.
            r = client.post(f"/api/invites/{token}/accept")
            assert r.status_code == 200
            assert r.json()["accepted_by_user_id"] == bob.id

            # Bob can now read and edit the plan.
            assert client.get(f"/api/plans/{plan_id}").status_code == 200
            r = client.post(
                f"/api/plans/{plan_id}/expenses",
                json={"name": "Bob added", "category": "basic", "amount": 100, "start_year": 2026},
            )
            assert r.status_code == 201


def test_double_accept_returns_410():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Double accept")

    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            token = client.post(
                f"/api/plans/{plan_id}/invites", json={"role": "viewer"}
            ).json()["token"]
        with _as_user(bob.firebase_uid, bob.email or ""):
            assert client.post(f"/api/invites/{token}/accept").status_code == 200
            r = client.post(f"/api/invites/{token}/accept")
            assert r.status_code == 410
            assert "accepted" in r.json()["detail"].lower()


def test_email_bound_invite_rejects_other_user():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    carol = _ensure_user("carol-uid", "carol@example.com")
    plan_id = _seed_plan_for(alice, "Email-bound")

    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            token = client.post(
                f"/api/plans/{plan_id}/invites",
                json={"role": "editor", "email": "carol@example.com"},
            ).json()["token"]

        # Bob can't accept Carol's invite.
        with _as_user(bob.firebase_uid, bob.email or ""):
            r = client.post(f"/api/invites/{token}/accept")
            assert r.status_code == 403

        # Carol can.
        with _as_user(carol.firebase_uid, carol.email or ""):
            assert client.post(f"/api/invites/{token}/accept").status_code == 200


def test_expired_invite_is_rejected():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Expired invite plan")

    # Create an invite directly in the DB with an expired timestamp.
    expired_token = token_urlsafe(16)
    with SessionLocal() as db:
        inv = PlanInvite(
            plan_id=plan_id,
            created_by_user_id=alice.id,
            role="editor",
            token=expired_token,
            expires_at=utcnow() - timedelta(days=1),
        )
        db.add(inv)
        db.commit()

    with TestClient(app) as client:
        with _as_user(bob.firebase_uid, bob.email or ""):
            assert client.get(f"/api/invites/{expired_token}").status_code == 410
            assert client.post(f"/api/invites/{expired_token}/accept").status_code == 410


def test_only_owner_can_create_invites():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Owner-only")

    # Make Bob an editor (not owner).
    from app.auth import grant_plan_membership

    with SessionLocal() as db:
        grant_plan_membership(db, plan_id, bob.id, role="editor")

    with TestClient(app) as client:
        with _as_user(bob.firebase_uid, bob.email or ""):
            r = client.post(f"/api/plans/{plan_id}/invites", json={"role": "viewer"})
            assert r.status_code == 403


# ---------- members ----------


def test_list_and_change_member_role():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Member mgmt")

    from app.auth import grant_plan_membership

    with SessionLocal() as db:
        grant_plan_membership(db, plan_id, bob.id, role="viewer")

    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            members = client.get(f"/api/plans/{plan_id}/members").json()
            roles = {m["user_id"]: m["role"] for m in members}
            assert roles[alice.id] == "owner"
            assert roles[bob.id] == "viewer"

            # Promote Bob to editor.
            r = client.patch(
                f"/api/plans/{plan_id}/members/{bob.id}", json={"role": "editor"}
            )
            assert r.status_code == 200
            assert r.json()["role"] == "editor"


def test_cannot_demote_last_owner():
    alice = _ensure_user("alice-uid", "alice@example.com")
    plan_id = _seed_plan_for(alice, "Last-owner test")

    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            r = client.patch(
                f"/api/plans/{plan_id}/members/{alice.id}", json={"role": "editor"}
            )
            assert r.status_code == 409


def test_cannot_remove_last_owner():
    alice = _ensure_user("alice-uid", "alice@example.com")
    plan_id = _seed_plan_for(alice, "Last-owner removal test")

    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            r = client.delete(f"/api/plans/{plan_id}/members/{alice.id}")
            assert r.status_code == 409


def test_member_can_self_leave():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    plan_id = _seed_plan_for(alice, "Self-leave")

    from app.auth import get_member_role, grant_plan_membership

    with SessionLocal() as db:
        grant_plan_membership(db, plan_id, bob.id, role="viewer")

    with TestClient(app) as client:
        with _as_user(bob.firebase_uid, bob.email or ""):
            r = client.delete(f"/api/plans/{plan_id}/members/{bob.id}")
            assert r.status_code == 204

    with SessionLocal() as db:
        assert get_member_role(db, plan_id, bob.id) is None


def test_owner_can_revoke_invite():
    alice = _ensure_user("alice-uid", "alice@example.com")
    plan_id = _seed_plan_for(alice, "Revoke test")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            inv = client.post(
                f"/api/plans/{plan_id}/invites", json={"role": "viewer"}
            ).json()
            assert client.delete(f"/api/invites/{inv['id']}").status_code == 204
            # Token now 404s.
            assert client.get(f"/api/invites/{inv['token']}").status_code == 404
