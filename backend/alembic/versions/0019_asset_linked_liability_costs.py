"""0019 asset linked liability + transaction costs

Phase 2 of property transactions. Adds to `assets`:
- linked_liability_id → the mortgage financing the property, settled on a planned
  sale (FK to liabilities, SET NULL on delete).
- stamp_duty_pct → charged on the purchase price (paid from cash on purchase).
- selling_cost_pct → agent/legal fees taken off the sale proceeds.

Revision ID: 0019_asset_txn2
Revises: 0018_asset_txn
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_asset_txn2"
down_revision: Union[str, Sequence[str], None] = "0018_asset_txn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("linked_liability_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column("stamp_duty_pct", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "assets",
        sa.Column("selling_cost_pct", sa.Float(), nullable=False, server_default="0"),
    )
    # Named FK so SQLite batch / Postgres both drop cleanly on downgrade.
    with op.batch_alter_table("assets") as batch:
        batch.create_foreign_key(
            "fk_assets_linked_liability_id",
            "liabilities",
            ["linked_liability_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch:
        batch.drop_constraint("fk_assets_linked_liability_id", type_="foreignkey")
    op.drop_column("assets", "selling_cost_pct")
    op.drop_column("assets", "stamp_duty_pct")
    op.drop_column("assets", "linked_liability_id")
