"""0015 person pension_option + annuity_rate

Adds:
- ``people.pension_option`` (str, not null, default 'arf'): what to do with the
  pension pot after the tax-free lump sum at retirement — "arf" (invest in an
  ARF and draw down), "annuity" (buy a lifetime annuity), or "taxable_lump_sum"
  (take the remainder as cash, taxed as income).
- ``people.annuity_rate`` (float, not null, default 0.04): annual annuity income
  as a fraction of the annuitised pot. Only used when pension_option == 'annuity'.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-06-16 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "pension_option",
                sa.String(),
                nullable=False,
                server_default="arf",
            )
        )
        batch_op.add_column(
            sa.Column(
                "annuity_rate",
                sa.Float(),
                nullable=False,
                server_default="0.04",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.drop_column("annuity_rate")
        batch_op.drop_column("pension_option")
