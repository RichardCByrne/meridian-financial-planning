"""0018 asset property transactions (purchase_year / deposit / disposal_year)

Adds planned-transaction columns to `assets` so a property (or any asset) can be
bought in a future year (dormant until then; deposit paid out of cash) and/or
deliberately sold in a chosen year (net proceeds into cash). Phase 1 of
move-house / second-home modelling.

Revision ID: 0018_asset_txn
Revises: 0017_liab_adj
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_asset_txn"
down_revision: Union[str, Sequence[str], None] = "0017_liab_adj"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("purchase_year", sa.Integer(), nullable=True))
    op.add_column(
        "assets",
        sa.Column("deposit", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column("assets", sa.Column("disposal_year", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "disposal_year")
    op.drop_column("assets", "deposit")
    op.drop_column("assets", "purchase_year")
