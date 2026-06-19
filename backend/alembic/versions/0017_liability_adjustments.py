"""0017 liability_adjustments (rate steps / overpayment changes / lump sums)

Adds the `liability_adjustments` child table. Each row is a time-keyed change to
a liability: a rate step (re-amortises the payment over the remaining term), an
overpayment change, or a one-off lump-sum capital repayment. Mirrors Voyant's
mortgage rate periods / overpayment events.

Revision ID: 0017_liab_adj
Revises: bb3ec9027b80
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_liab_adj"
down_revision: Union[str, Sequence[str], None] = "bb3ec9027b80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "liability_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "liability_id",
            sa.Integer(),
            sa.ForeignKey("liabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("effective_year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
    )
    op.create_index(
        "ix_liability_adjustments_liability_id",
        "liability_adjustments",
        ["liability_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_liability_adjustments_liability_id",
        table_name="liability_adjustments",
    )
    op.drop_table("liability_adjustments")
