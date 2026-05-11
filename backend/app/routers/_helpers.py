"""Cross-router helpers."""

from __future__ import annotations

from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import Base

T = TypeVar("T", bound=Base)


def get_or_404(model: type[T], pk: int, db: Session, *, name: str | None = None) -> T:
    """Fetch `model` by primary key or raise 404. `name` overrides the detail label."""
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{name or model.__name__} not found")
    return obj
