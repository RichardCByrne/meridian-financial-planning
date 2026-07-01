"""People router CRUD + authz.

Covers previously-untested update / delete happy paths and the role guards.
"""

from fastapi.testclient import TestClient

from app.auth import grant_plan_membership
from app.db import SessionLocal
from app.main import app
from app.tests._authz_helpers import as_user, ensure_user


def _seed_plan(client: TestClient) -> int:
    return client.post(
        "/api/plans",
        json={"name": "People plan", "base_year": 2026, "projection_years": 5},
    ).json()["id"]


def _person_payload(name: str = "Liam") -> dict:
    return {"name": name, "dob": "1990-01-01", "is_primary": True, "retirement_age": 66}


def test_person_create_update_delete_roundtrip():
    with TestClient(app) as client:
        pid = _seed_plan(client)
        created = client.post(f"/api/plans/{pid}/people", json=_person_payload())
        assert created.status_code == 201
        person_id = created.json()["id"]

        upd = client.patch(f"/api/people/{person_id}", json={"retirement_age": 68})
        assert upd.status_code == 200
        assert upd.json()["retirement_age"] == 68
        assert upd.json()["name"] == "Liam"

        assert client.delete(f"/api/people/{person_id}").status_code == 204
        assert client.get(f"/api/plans/{pid}/people").json() == []


def test_person_patch_and_delete_missing_returns_404():
    with TestClient(app) as client:
        _seed_plan(client)
        assert client.patch("/api/people/999999", json={"retirement_age": 68}).status_code == 404
        assert client.delete("/api/people/999999").status_code == 404


def test_person_viewer_cannot_write():
    alice = ensure_user("alice-uid", "alice@example.com")
    bob = ensure_user("bob-uid", "bob@example.com")
    with TestClient(app) as client:
        with as_user(alice.firebase_uid, alice.email or ""):
            pid = _seed_plan(client)
            person_id = client.post(f"/api/plans/{pid}/people", json=_person_payload()).json()["id"]

        with SessionLocal() as db:
            grant_plan_membership(db, pid, bob.id, role="viewer")

        with as_user(bob.firebase_uid, bob.email or ""):
            assert client.get(f"/api/plans/{pid}/people").status_code == 200
            assert client.post(f"/api/plans/{pid}/people", json=_person_payload("X")).status_code == 403
            assert client.patch(f"/api/people/{person_id}", json={"retirement_age": 68}).status_code == 403
            assert client.delete(f"/api/people/{person_id}").status_code == 403


def test_person_non_member_gets_404():
    alice = ensure_user("alice-uid", "alice@example.com")
    mallory = ensure_user("mallory-uid", "mallory@example.com")
    with TestClient(app) as client:
        with as_user(alice.firebase_uid, alice.email or ""):
            pid = _seed_plan(client)
            person_id = client.post(f"/api/plans/{pid}/people", json=_person_payload()).json()["id"]

        with as_user(mallory.firebase_uid, mallory.email or ""):
            assert client.get(f"/api/plans/{pid}/people").status_code == 404
            assert client.patch(f"/api/people/{person_id}", json={"retirement_age": 68}).status_code == 404
            assert client.delete(f"/api/people/{person_id}").status_code == 404
