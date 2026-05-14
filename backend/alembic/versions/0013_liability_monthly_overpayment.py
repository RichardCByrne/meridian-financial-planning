"""0013 liability monthly_overpayment

Adds:
- ``liabilities.monthly_overpayment`` (float, default 0.0): extra €/mo applied
  directly to capital, shortens the loan term. Default 0 preserves the
  original "pay the contracted monthly amount" behaviour.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-05-14 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("liabilities", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "monthly_overpayment",
                sa.Float(),
                nullable=False,
                server_default="0.0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("liabilities", schema=None) as batch_op:
        batch_op.drop_column("monthly_overpayment")
