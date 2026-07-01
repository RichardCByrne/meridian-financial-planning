"""Income router CRUD + authz.

Income is created under a person (/people/{id}/income); updates/deletes are by
income id. Covers previously-untested update / delete paths and role guards.
"""

from fastapi.testclient import TestClient

from app.auth import grant_plan_membership
from app.db import SessionLocal
from app.main import app
from app.tests._authz_helpers import as_user, ensure_user


def _seed_plan_and_person(client: TestClient) -> tuple[int, int]:
    pid = client.post(
        "/api/plans",
        json={"name": "Income plan", "base_year": 2026, "projection_years": 5},
    ).json()["id"]
    person_id = client.post(
        f"/api/plans/{pid}/people",
        json={"name": "Niamh", "dob": "1990-01-01", "is_primary": True},
    ).json()["id"]
    return pid, person_id


def _income_payload(name: str = "Salary") -> dict:
    return {"kind": "employment", "name": name, "gross_amount": 60_000, "start_year": 2026}


def test_income_create_update_delete_roundtrip():
    with TestClient(app) as client:
        _, person_id = _seed_plan_and_person(client)
        created = client.post(f"/api/people/{person_id}/income", json=_income_payload())
        assert created.status_code == 201
        income_id = created.json()["id"]

        upd = client.patch(f"/api/income/{income_id}", json={"gross_amount": 70_000})
        assert upd.status_code == 200
        assert upd.json()["gross_amount"] == 70_000
        assert upd.json()["name"] == "Salary"

        assert client.delete(f"/api/income/{income_id}").status_code == 204
        assert client.get(f"/api/people/{person_id}/income").json() == []


def test_income_patch_and_delete_missing_returns_404():
    with TestClient(app) as client:
        _seed_plan_and_person(client)
        assert client.patch("/api/income/999999", json={"gross_amount": 1}).status_code == 404
        assert client.delete("/api/income/999999").status_code == 404


def test_income_viewer_cannot_write():
    alice = ensure_user("alice-uid", "alice@example.com")
    bob = ensure_user("bob-uid", "bob@example.com")
    with TestClient(app) as client:
        with as_user(alice.firebase_uid, alice.email or ""):
            pid, person_id = _seed_plan_and_person(client)
            income_id = client.post(f"/api/people/{person_id}/income", json=_income_payload()).json()["id"]

        with SessionLocal() as db:
            grant_plan_membership(db, pid, bob.id, role="viewer")

        with as_user(bob.firebase_uid, bob.email or ""):
            assert client.get(f"/api/people/{person_id}/income").status_code == 200
            assert client.post(f"/api/people/{person_id}/income", json=_income_payload("X")).status_code == 403
            assert client.patch(f"/api/income/{income_id}", json={"gross_amount": 1}).status_code == 403
            assert client.delete(f"/api/income/{income_id}").status_code == 403


def test_income_non_member_gets_404():
    alice = ensure_user("alice-uid", "alice@example.com")
    mallory = ensure_user("mallory-uid", "mallory@example.com")
    with TestClient(app) as client:
        with as_user(alice.firebase_uid, alice.email or ""):
            pid, person_id = _seed_plan_and_person(client)
            income_id = client.post(f"/api/people/{person_id}/income", json=_income_payload()).json()["id"]

        with as_user(mallory.firebase_uid, mallory.email or ""):
            assert client.get(f"/api/people/{person_id}/income").status_code == 404
            assert client.patch(f"/api/income/{income_id}", json={"gross_amount": 1}).status_code == 404
            assert client.delete(f"/api/income/{income_id}").status_code == 404
