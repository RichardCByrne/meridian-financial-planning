"""0021 benefits table (benefit-in-kind)

Adds a dedicated ``benefits`` table for employer-provided benefits-in-kind
(BIK): employer-paid medical insurance, company car/van, preferential loans,
and other perks. Each benefit is attached to a ``people`` row. The simulator
charges the cash equivalent to the employee as notional pay (IT + USC + PRSI)
without adding it to cash flow, and grants the 20% (capped) medical-insurance
relief credit on employer-paid premiums. See engine/bik_ie.py.

Revision ID: 0021_benefits
Revises: 0020_income_bonus
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_benefits"
down_revision: Union[str, Sequence[str], None] = "0020_income_bonus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: lightweight create_all may have built this table already while
    # alembic_version trails this revision.
    if sa.inspect(op.get_bind()).has_table("benefits"):
        return
    op.create_table(
        "benefits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            sa.Integer(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("start_year", sa.Integer(), nullable=False),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("escalation_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("omv", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "loan_is_qualifying", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("relief_adults", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("relief_children", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("benefits")
