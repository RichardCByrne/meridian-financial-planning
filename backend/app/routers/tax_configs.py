"""CRUD for `TaxConfigRow`. Listing returns the seeded official + the caller's
own configs. Editing is allowed only on user-owned configs (not the official).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.engine.tax_config import TaxConfig
from app.models import Plan, TaxConfigRow, User
from app.routers._helpers import get_or_404
from app.schemas.tax_config import TaxConfigCreate, TaxConfigRead, TaxConfigUpdate

router = APIRouter(prefix="/tax-configs", tags=["tax-configs"])


@router.get("", response_model=list[TaxConfigRead])
def list_tax_configs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaxConfigRow]:
    """Return seeded official configs plus configs the caller owns."""
    return list(
        db.execute(
            select(TaxConfigRow)
            .where(
                or_(
                    TaxConfigRow.is_official.is_(True),
                    TaxConfigRow.created_by_user_id == user.id,
                )
            )
            .order_by(TaxConfigRow.is_official.desc(), TaxConfigRow.name)
        ).scalars()
    )


@router.get("/{config_id}", response_model=TaxConfigRead)
def get_tax_config(
    config_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxConfigRow:
    row = get_or_404(TaxConfigRow, config_id, db, name="Tax config")
    if not row.is_official and row.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Tax config not found")
    return row


@router.post("", response_model=TaxConfigRead, status_code=status.HTTP_201_CREATED)
def create_tax_config(
    payload: TaxConfigCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxConfigRow:
    """Clone an existing config (default: official seed) and start a user-owned copy."""
    base_payload: dict
    if payload.clone_from_id is not None:
        base = get_or_404(TaxConfigRow, payload.clone_from_id, db, name="Tax config")
        if not base.is_official and base.created_by_user_id != user.id:
            raise HTTPException(status_code=404, detail="Source config not found")
        base_payload = dict(base.config_json)
    else:
        from app.config.tax_ie_2026 import IRELAND_2026_OFFICIAL

        base_payload = IRELAND_2026_OFFICIAL.to_dict()

    if payload.config:
        base_payload.update(payload.config)

    # Validate by round-tripping through the dataclass — rejects malformed data.
    try:
        validated = TaxConfig.from_dict({**base_payload, "name": payload.name})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid tax config payload: {e}") from e

    row = TaxConfigRow(
        name=payload.name,
        is_official=False,
        created_by_user_id=user.id,
        config_json=validated.to_dict(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{config_id}", response_model=TaxConfigRead)
def update_tax_config(
    config_id: int,
    payload: TaxConfigUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxConfigRow:
    row = get_or_404(TaxConfigRow, config_id, db, name="Tax config")
    if row.is_official:
        raise HTTPException(status_code=403, detail="The official config is read-only")
    if row.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Tax config not found")

    if payload.name is not None:
        row.name = payload.name
    if payload.config is not None:
        merged = {**row.config_json, **payload.config}
        try:
            validated = TaxConfig.from_dict({**merged, "name": row.name})
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Invalid tax config payload: {e}") from e
        row.config_json = validated.to_dict()
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tax_config(
    config_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    row = get_or_404(TaxConfigRow, config_id, db, name="Tax config")
    if row.is_official:
        raise HTTPException(status_code=403, detail="The official config cannot be deleted")
    if row.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Tax config not found")
    # If any plans still reference this config, NULL out their FK so they fall
    # back to the official seed rather than orphaning the plan.
    db.execute(
        update(Plan).where(Plan.tax_config_id == config_id).values(tax_config_id=None)
    )
    db.delete(row)
    db.commit()
