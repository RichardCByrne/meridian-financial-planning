"""Cross-router helpers."""

from __future__ import annotations

from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import Base
from app.models import TaxConfigRow

T = TypeVar("T", bound=Base)


def get_or_404(model: type[T], pk: int, db: Session, *, name: str | None = None) -> T:
    """Fetch `model` by primary key or raise 404. `name` overrides the detail label."""
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{name or model.__name__} not found")
    return obj


def tax_config_accessible(tax_config_id: int | None, user_id: int, db: Session) -> bool:
    """True if `user_id` may pin `tax_config_id`: no pin, the seeded official,
    or a config the caller owns. Non-raising counterpart of
    `assert_tax_config_accessible` — used where an inaccessible pin should be
    dropped rather than rejected (clone / import)."""
    if tax_config_id is None:
        return True
    row = db.get(TaxConfigRow, tax_config_id)
    return row is not None and (row.is_official or row.created_by_user_id == user_id)


def assert_tax_config_accessible(
    tax_config_id: int | None, user_id: int, db: Session
) -> None:
    """Guard a plan's `tax_config_id` write.

    A plan may only pin the seeded official config or one the caller owns.
    Without this, a user could point their plan at another user's private
    TaxConfigRow and infer its private band/rate values from projection output.

    `None` (no pin) is always allowed. Raises 404 — not 403 — for a config the
    caller can't use, matching the enumeration-safe convention used elsewhere:
    don't reveal that someone else's config id exists.
    """
    if not tax_config_accessible(tax_config_id, user_id, db):
        raise HTTPException(status_code=404, detail="Tax config not found")
