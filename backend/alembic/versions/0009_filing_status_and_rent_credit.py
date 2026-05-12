"""0009 plan filing_status + person claims_rent_credit

Adds:
- ``plans.filing_status`` (nullable string): "single" | "married" | "cohabiting".
  NULL preserves the legacy auto-detection (1 person → single, 2+ → married).
- ``people.claims_rent_credit`` (bool, default False): Irish rent tax credit
  flag (€1,000/yr from Budget 2024).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-10 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.add_column(sa.Column("filing_status", sa.String(length=20), nullable=True))
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "claims_rent_credit",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.drop_column("claims_rent_credit")
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.drop_column("filing_status")
