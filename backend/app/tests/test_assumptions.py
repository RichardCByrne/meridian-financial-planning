"""Assumptions router: GET auto-create + PUT upsert + authz gates.

The assumptions row feeds engine inputs (inflation, growth, earnings growth,
state pension). Both endpoints and their role guards were previously untested
(router at ~35% coverage). Covers:

- GET auto-creates a default row when none exists, and returns it thereafter.
- PUT inserts on first call, updates in place on the second.
- viewer role is blocked from PUT (editor gate); non-members get 404 (not 403,
  to avoid leaking plan ids).
- 404 for missing plan; 422 for out-of-range values.
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
    user = _ensure_user(firebase_uid, email)

    def _override():
        with SessionLocal() as db:
            return db.query(User).filter(User.id == user.id).one()

    app.dependency_overrides[get_current_user] = _override
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _seed_plan(client: TestClient) -> int:
    return client.post(
        "/api/plans",
        json={"name": "Assumptions plan", "base_year": 2026, "projection_years": 1},
    ).json()["id"]


def test_get_auto_creates_default_assumptions():
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            plan_id = _seed_plan(client)

            r = client.get(f"/api/plans/{plan_id}/assumptions")
            assert r.status_code == 200
            body = r.json()
            # Schema defaults land on the auto-created row.
            assert body["plan_id"] == plan_id
            assert body["inflation_rate"] == 0.025
            assert body["default_growth_rate"] == 0.05
            assert body["state_pension_age"] == 66

            # Second GET returns the same persisted row, not a fresh one.
            r2 = client.get(f"/api/plans/{plan_id}/assumptions")
            assert r2.status_code == 200
            assert r2.json()["id"] == body["id"]


def test_put_inserts_then_updates_in_place():
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            plan_id = _seed_plan(client)

            # First PUT with no pre-existing row: insert branch.
            insert_payload = {
                "inflation_rate": 0.03,
                "default_growth_rate": 0.06,
                "property_growth_rate": 0.04,
                "earnings_growth": 0.02,
                "state_pension_age": 67,
                "state_pension_annual_amount": 16_000.0,
                "state_pension_escalation_rate": 0.02,
            }
            r = client.put(f"/api/plans/{plan_id}/assumptions", json=insert_payload)
            assert r.status_code == 200
            created = r.json()
            assert created["inflation_rate"] == 0.03
            assert created["state_pension_age"] == 67

            # Second PUT: update branch mutates the same row (id stable).
            update_payload = dict(insert_payload, inflation_rate=0.01, state_pension_age=68)
            r2 = client.put(f"/api/plans/{plan_id}/assumptions", json=update_payload)
            assert r2.status_code == 200
            updated = r2.json()
            assert updated["id"] == created["id"]
            assert updated["inflation_rate"] == 0.01
            assert updated["state_pension_age"] == 68

            # GET reflects the update.
            assert client.get(f"/api/plans/{plan_id}/assumptions").json()["inflation_rate"] == 0.01


def test_put_rejects_out_of_range_value():
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            plan_id = _seed_plan(client)
            # inflation_rate le=0.5 per schema.
            r = client.put(
                f"/api/plans/{plan_id}/assumptions",
                json={"inflation_rate": 5.0},
            )
            assert r.status_code == 422


def test_missing_plan_returns_404():
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            assert client.get("/api/plans/999999/assumptions").status_code == 404
            assert (
                client.put("/api/plans/999999/assumptions", json={}).status_code == 404
            )


def test_viewer_cannot_upsert_assumptions():
    alice = _ensure_user("alice-uid", "alice@example.com")
    bob = _ensure_user("bob-uid", "bob@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            plan_id = _seed_plan(client)

        with SessionLocal() as db:
            grant_plan_membership(db, plan_id, bob.id, role="viewer")

        with _as_user(bob.firebase_uid, bob.email or ""):
            # Viewer may read...
            assert client.get(f"/api/plans/{plan_id}/assumptions").status_code == 200
            # ...but not write (editor gate).
            r = client.put(
                f"/api/plans/{plan_id}/assumptions",
                json={"inflation_rate": 0.04},
            )
            assert r.status_code == 403


def test_non_member_gets_404_not_403():
    alice = _ensure_user("alice-uid", "alice@example.com")
    mallory = _ensure_user("mallory-uid", "mallory@example.com")
    with TestClient(app) as client:
        with _as_user(alice.firebase_uid, alice.email or ""):
            plan_id = _seed_plan(client)

        with _as_user(mallory.firebase_uid, mallory.email or ""):
            # Non-member: 404 to avoid leaking plan existence.
            assert client.get(f"/api/plans/{plan_id}/assumptions").status_code == 404
            assert (
                client.put(
                    f"/api/plans/{plan_id}/assumptions", json={"inflation_rate": 0.04}
                ).status_code
                == 404
            )
