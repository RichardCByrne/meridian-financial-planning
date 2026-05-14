"""0011 person prsi_weeks_at_base_year + homecaring_weeks_at_base_year

Adds two integer columns on ``people`` to seed the Total Contributions Approach
state-pension calculation:

- ``prsi_weeks_at_base_year`` (int, default 2080): PRSI weeks already accrued
  before the projection starts. Default 2080 = 40 years = full TCA cap, which
  preserves the legacy "everyone gets the full state pension" behaviour.
- ``homecaring_weeks_at_base_year`` (int, default 0): HomeCaring credit weeks
  already accrued before the projection starts. Capped at 1,040 (20 years).

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-14 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "prsi_weeks_at_base_year",
                sa.Integer(),
                nullable=False,
                server_default="2080",
            )
        )
        batch_op.add_column(
            sa.Column(
                "homecaring_weeks_at_base_year",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.drop_column("homecaring_weeks_at_base_year")
        batch_op.drop_column("prsi_weeks_at_base_year")
