"""Phase 14 prep tests: editable filing_status on Plan.

Exercises the PATCH /plans/{id} transition flow:
- Plan can be created with any filing status (or null = auto).
- Status can transition between single / married / cohabiting / null via PATCH.
- The simulator picks up the change on the next projection.
"""

from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.auth import get_current_user
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


def _seed_two_person_plan(client: TestClient, filing_status: str | None) -> int:
    """Create a plan + 2 people + 1 income so projections can differentiate filing modes."""
    payload = {"name": "Household", "base_year": 2026, "projection_years": 1}
    if filing_status is not None:
        payload["filing_status"] = filing_status
    plan_id = client.post("/api/plans", json=payload).json()["id"]
    for name, dob, primary in [("Aoife", "1990-01-01", True), ("Conor", "1992-01-01", False)]:
        client.post(
            f"/api/plans/{plan_id}/people",
            json={
                "name": name,
                "dob": dob,
                "is_primary": primary,
                "life_expectancy": 90,
                "retirement_age": 66,
                "claims_rent_credit": False,
            },
        )
    aoife_id = client.get(f"/api/plans/{plan_id}/people").json()[0]["id"]
    client.post(
        f"/api/people/{aoife_id}/income",
        json={
            "kind": "employment",
            "name": "Job",
            "gross_amount": 70_000,
            "start_year": 2026,
            "end_year": None,
            "escalation_rate": 0.0,
            "pays_prsi": True,
            "pays_usc": True,
            "pension_contribution_pct": 0.0,
            "employer_pension_contribution_pct": 0.0,
        },
    )
    return plan_id


def test_filing_status_can_be_set_on_creation():
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client, _as_user(alice.firebase_uid, alice.email or ""):
        for status in ("single", "married", "cohabiting"):
            r = client.post(
                "/api/plans",
                json={"name": f"Plan {status}", "filing_status": status},
            )
            assert r.status_code == 201
            assert r.json()["filing_status"] == status


def test_filing_status_transitions_via_patch():
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client, _as_user(alice.firebase_uid, alice.email or ""):
        plan_id = client.post(
            "/api/plans", json={"name": "Transition", "filing_status": "cohabiting"}
        ).json()["id"]

        # cohabiting → married
        r = client.patch(f"/api/plans/{plan_id}", json={"filing_status": "married"})
        assert r.status_code == 200
        assert r.json()["filing_status"] == "married"
        assert client.get(f"/api/plans/{plan_id}").json()["filing_status"] == "married"

        # married → single
        client.patch(f"/api/plans/{plan_id}", json={"filing_status": "single"})
        assert client.get(f"/api/plans/{plan_id}").json()["filing_status"] == "single"

        # single → null (auto)
        client.patch(f"/api/plans/{plan_id}", json={"filing_status": None})
        assert client.get(f"/api/plans/{plan_id}").json()["filing_status"] is None

        # null → cohabiting (round trip)
        client.patch(f"/api/plans/{plan_id}", json={"filing_status": "cohabiting"})
        assert client.get(f"/api/plans/{plan_id}").json()["filing_status"] == "cohabiting"


def test_invalid_filing_status_rejected():
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client, _as_user(alice.firebase_uid, alice.email or ""):
        plan_id = client.post("/api/plans", json={"name": "Bad"}).json()["id"]
        r = client.patch(f"/api/plans/{plan_id}", json={"filing_status": "domestic_partnership"})
        assert r.status_code == 422


def test_patch_to_cohabiting_increases_projected_tax():
    """End-to-end: switching from married (auto for 2 people) to cohabiting raises
    income tax because cohabiting couples are taxed individually."""
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client, _as_user(alice.firebase_uid, alice.email or ""):
        plan_id = _seed_two_person_plan(client, filing_status=None)  # auto → married

        before = client.get(f"/api/plans/{plan_id}/projection").json()
        married_tax = before["years"][0]["income_tax"]

        client.patch(f"/api/plans/{plan_id}", json={"filing_status": "cohabiting"})

        after = client.get(f"/api/plans/{plan_id}/projection").json()
        cohab_tax = after["years"][0]["income_tax"]

        # Same income, narrower band → more tax. Ballpark gap > €3k.
        assert cohab_tax > married_tax
        assert cohab_tax - married_tax > 3_000


def test_patch_filing_status_does_not_clobber_other_fields():
    """PATCH with only filing_status must leave name / projection_years / tax_config_id alone."""
    alice = _ensure_user("alice-uid", "alice@example.com")
    with TestClient(app) as client, _as_user(alice.firebase_uid, alice.email or ""):
        plan_id = client.post(
            "/api/plans",
            json={"name": "Untouched", "base_year": 2027, "projection_years": 12},
        ).json()["id"]

        client.patch(f"/api/plans/{plan_id}", json={"filing_status": "married"})

        plan = client.get(f"/api/plans/{plan_id}").json()
        assert plan["name"] == "Untouched"
        assert plan["base_year"] == 2027
        assert plan["projection_years"] == 12
        assert plan["filing_status"] == "married"
