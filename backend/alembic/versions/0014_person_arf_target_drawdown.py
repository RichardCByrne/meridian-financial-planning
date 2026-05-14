"""0014 person arf_target_drawdown_pct

Adds:
- ``people.arf_target_drawdown_pct`` (float, nullable): voluntary ARF drawdown
  rate. NULL = use the statutory minimum only (4% / 5% / 6%). When set, the
  engine takes max(statutory_minimum, target) each post-retirement year.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-05-14 17:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("arf_target_drawdown_pct", sa.Float(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.drop_column("arf_target_drawdown_pct")
