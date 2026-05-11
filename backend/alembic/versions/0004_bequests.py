"""0004 bequests

Revision ID: f1b92c3e4d75
Revises: e4435d80c034
Create Date: 2026-05-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1b92c3e4d75"
down_revision: Union[str, Sequence[str], None] = "e4435d80c034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bequests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("from_person_id", sa.Integer(), nullable=False),
        sa.Column("to_person_id", sa.Integer(), nullable=True),
        sa.Column("cat_group", sa.String(length=10), nullable=False),
        sa.Column("share_pct", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["from_person_id"], ["people.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_person_id"], ["people.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("bequests")
