"""0026 asset annual product charge

Adds `assets.annual_charge_pct` — the total annual product charge (AMC +
platform + adviser fee) as a fraction of balance, deducted from growth each
year so pots compound net of charges. Default 0.0 leaves existing plans
unchanged.

Revision ID: 0026_asset_charge
Revises: 0025_drop_legacy_exp_cat
Create Date: 2026-07-01

Note: the revision id is kept <=32 chars because Alembic's
``alembic_version.version_num`` column is ``VARCHAR(32)`` on Postgres — a
longer id raises StringDataRightTruncation when the version is stamped.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_asset_charge"
down_revision: Union[str, Sequence[str], None] = "0025_drop_legacy_exp_cat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    # Idempotent: lightweight create_all may have added this already while
    # alembic_version trails this revision.
    if not _has_column("assets", "annual_charge_pct"):
        op.add_column(
            "assets",
            sa.Column("annual_charge_pct", sa.Float(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("assets", "annual_charge_pct")
