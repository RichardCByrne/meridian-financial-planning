"""0012 children table

Adds a dedicated ``children`` table for child entities (separate from
``people``). Each child has a DOB and an optional primary_carer_id FK to a
``people`` row. The simulator reads this list to pay tax-free Child Benefit
to the carer (€140/mo × 12 per child under 18, escalated).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-14 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "children",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("dob", sa.Date(), nullable=False),
        sa.Column(
            "primary_carer_id",
            sa.Integer(),
            sa.ForeignKey("people.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("children")
