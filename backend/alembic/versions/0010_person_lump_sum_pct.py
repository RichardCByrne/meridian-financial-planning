"""0010 person lump_sum_pct

Adds:
- ``people.lump_sum_pct`` (float, default 0.25): fraction of pension pot a
  person takes as a tax-free lump sum at retirement. Irish rules cap at 25%;
  lower values leave more in the ARF.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-14 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "lump_sum_pct",
                sa.Float(),
                nullable=False,
                server_default="0.25",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.drop_column("lump_sum_pct")
