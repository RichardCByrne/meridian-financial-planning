"""0006 asset contributions

Revision ID: b2c3d4e5f6a7
Revises: a9c1d2e3f4b5
Create Date: 2026-05-07 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a9c1d2e3f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("annual_contribution", sa.Float(), nullable=False, server_default="0.0")
        )
        batch_op.add_column(
            sa.Column(
                "contribution_pct_of_net_income", sa.Float(), nullable=False, server_default="0.0"
            )
        )
        batch_op.add_column(sa.Column("contribution_start_year", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("contribution_end_year", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_column("contribution_end_year")
        batch_op.drop_column("contribution_start_year")
        batch_op.drop_column("contribution_pct_of_net_income")
        batch_op.drop_column("annual_contribution")
