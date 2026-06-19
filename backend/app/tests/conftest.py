"""Per-test DB cleanup.

The dev SQLite file is shared across the whole test session because the app
factory + lifespan singletons make swapping engines awkward. Without
intervention, rows created by one test leak into the next — e.g.
`test_phase8` creates a plan named "Alice's plan" and the next test sees
it in Alice's `GET /api/plans` listing.

This autouse fixture wipes all data tables after each test. The seeded
`IRELAND_2026_OFFICIAL` `TaxConfigRow` is recreated on demand by the
lifespan hook the next time a test enters `TestClient(app)`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.models import (
    Asset,
    Assumptions,
    Benefit,
    Bequest,
    Expense,
    Goal,
    IncomeSource,
    Liability,
    LiabilityAdjustment,
    Person,
    Plan,
    PlanInvite,
    PlanMember,
    Scenario,
    TaxConfigRow,
    User,
)

# Children first so even with FK enforcement off (SQLite default) no orphan
# rows linger after a partial run. Plan + Person are deleted last because
# almost everything points at them.
_WIPE_ORDER = (
    PlanInvite,
    PlanMember,
    Benefit,
    Bequest,
    Goal,
    Scenario,
    LiabilityAdjustment,
    Liability,
    Asset,
    IncomeSource,
    Expense,
    Assumptions,
    Person,
    Plan,
    TaxConfigRow,
    User,
)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    yield
    with SessionLocal() as db:
        for model in _WIPE_ORDER:
            db.execute(delete(model))
        db.commit()
