"""Smoke tests for the Monte-Carlo response cache in routers/projections."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.db import SessionLocal
from app.main import app
from app.models import Assumptions, Person, Plan, User
from app.routers.projections import _mc_cache, _mc_cache_clear


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


def _seed_plan(owner_id: int) -> int:
    from app.models import PlanMember

    with SessionLocal() as db:
        plan = Plan(name="MC cache plan", base_year=2026, projection_years=3)
        db.add(plan)
        db.flush()
        db.add(Assumptions(plan_id=plan.id))
        db.add(Person(plan_id=plan.id, name="A", dob=date(1990, 1, 1), is_primary=True))
        db.add(PlanMember(plan_id=plan.id, user_id=owner_id, role="owner"))
        db.commit()
        return plan.id


def test_mc_cache_hits_within_ttl():
    """Two identical Monte-Carlo requests in quick succession reuse the cached response."""
    _mc_cache_clear()
    with _as_user("mc-cache-user", "mc@example.com") as user:
        plan_id = _seed_plan(user.id)
        with TestClient(app) as client:
            r1 = client.get(f"/api/plans/{plan_id}/projection/montecarlo?n=20&seed=1")
            assert r1.status_code == 200, r1.text
            r2 = client.get(f"/api/plans/{plan_id}/projection/montecarlo?n=20&seed=1")
            assert r2.status_code == 200, r2.text
            # Same response, single cache entry
            assert r1.json() == r2.json()
            assert len(_mc_cache) == 1


def test_mc_cache_differs_by_parameters():
    """Changing n or seed produces distinct cache entries."""
    _mc_cache_clear()
    with _as_user("mc-cache-user2", "mc2@example.com") as user:
        plan_id = _seed_plan(user.id)
        with TestClient(app) as client:
            client.get(f"/api/plans/{plan_id}/projection/montecarlo?n=20&seed=1")
            client.get(f"/api/plans/{plan_id}/projection/montecarlo?n=20&seed=2")
            client.get(f"/api/plans/{plan_id}/projection/montecarlo?n=50&seed=1")
            assert len(_mc_cache) == 3


def test_mc_cache_expires():
    """Cache entries past TTL are evicted on read."""
    import time as _time
    from app.routers import projections as proj

    _mc_cache_clear()
    with _as_user("mc-cache-user3", "mc3@example.com") as user:
        plan_id = _seed_plan(user.id)
        with TestClient(app) as client:
            client.get(f"/api/plans/{plan_id}/projection/montecarlo?n=20&seed=1")
            assert len(_mc_cache) == 1
            # Force-expire by rewriting the entry with a past timestamp.
            key = next(iter(_mc_cache))
            _, value = _mc_cache[key]
            _mc_cache[key] = (_time.monotonic() - 1, value)
            assert proj._mc_cache_get(key) is None
            assert len(_mc_cache) == 0
