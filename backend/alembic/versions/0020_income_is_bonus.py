"""0020 income_sources.is_bonus

Adds a UI marker flagging an income row as a bonus (still a normal taxable
income; the engine ignores the flag). Lets the editor badge bonuses and offer a
one-click bonus shortcut.

Revision ID: 0020_income_bonus
Revises: 0019_asset_txn2
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_income_bonus"
down_revision: Union[str, Sequence[str], None] = "0019_asset_txn2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "income_sources",
        sa.Column("is_bonus", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("income_sources", "is_bonus")
