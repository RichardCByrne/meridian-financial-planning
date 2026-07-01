"""Expenses router CRUD + authz.

Covers the previously-untested update / delete happy paths and the role
guards (editor gate on writes, non-member 404, 404 on missing rows).
"""

from fastapi.testclient import TestClient

from app.auth import grant_plan_membership
from app.db import SessionLocal
from app.main import app
from app.tests._authz_helpers import as_user, ensure_user


def _seed_plan(client: TestClient) -> int:
    return client.post(
        "/api/plans",
        json={"name": "Expenses plan", "base_year": 2026, "projection_years": 5},
    ).json()["id"]


def test_expense_create_update_delete_roundtrip():
    with TestClient(app) as client:
        pid = _seed_plan(client)
        created = client.post(
            f"/api/plans/{pid}/expenses",
            json={"name": "Rent", "category": "basic", "amount": 24_000, "start_year": 2026},
        )
        assert created.status_code == 201
        eid = created.json()["id"]

        upd = client.patch(f"/api/expenses/{eid}", json={"amount": 26_000})
        assert upd.status_code == 200
        assert upd.json()["amount"] == 26_000
        assert upd.json()["name"] == "Rent"  # untouched fields preserved

        assert client.delete(f"/api/expenses/{eid}").status_code == 204
        assert client.get(f"/api/plans/{pid}/expenses").json() == []


def test_expense_patch_and_delete_missing_returns_404():
    with TestClient(app) as client:
        _seed_plan(client)
        assert client.patch("/api/expenses/999999", json={"amount": 1}).status_code == 404
        assert client.delete("/api/expenses/999999").status_code == 404


def test_expense_viewer_cannot_write():
    alice = ensure_user("alice-uid", "alice@example.com")
    bob = ensure_user("bob-uid", "bob@example.com")
    with TestClient(app) as client:
        with as_user(alice.firebase_uid, alice.email or ""):
            pid = _seed_plan(client)
            eid = client.post(
                f"/api/plans/{pid}/expenses",
                json={"name": "Rent", "category": "basic", "amount": 24_000, "start_year": 2026},
            ).json()["id"]

        with SessionLocal() as db:
            grant_plan_membership(db, pid, bob.id, role="viewer")

        with as_user(bob.firebase_uid, bob.email or ""):
            assert client.get(f"/api/plans/{pid}/expenses").status_code == 200
            assert (
                client.post(
                    f"/api/plans/{pid}/expenses",
                    json={"name": "X", "category": "basic", "amount": 1, "start_year": 2026},
                ).status_code
                == 403
            )
            assert client.patch(f"/api/expenses/{eid}", json={"amount": 1}).status_code == 403
            assert client.delete(f"/api/expenses/{eid}").status_code == 403


def test_expense_non_member_gets_404():
    alice = ensure_user("alice-uid", "alice@example.com")
    mallory = ensure_user("mallory-uid", "mallory@example.com")
    with TestClient(app) as client:
        with as_user(alice.firebase_uid, alice.email or ""):
            pid = _seed_plan(client)
            eid = client.post(
                f"/api/plans/{pid}/expenses",
                json={"name": "Rent", "category": "basic", "amount": 24_000, "start_year": 2026},
            ).json()["id"]

        with as_user(mallory.firebase_uid, mallory.email or ""):
            # List leaks nothing: 404, not 403.
            assert client.get(f"/api/plans/{pid}/expenses").status_code == 404
            assert client.patch(f"/api/expenses/{eid}", json={"amount": 1}).status_code == 404
            assert client.delete(f"/api/expenses/{eid}").status_code == 404
