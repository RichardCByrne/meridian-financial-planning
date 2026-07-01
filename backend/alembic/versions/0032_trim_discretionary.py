"""0032 plan trim_discretionary_on_shortfall flag

Adds plans.trim_discretionary_on_shortfall — needs-vs-wants funding floor: when
true, a year that can't be fully funded trims discretionary spending before
declaring a shortfall (essentials protected). Default False = unchanged.

Revision ID: 0032_trim_discretionary
Revises: 0031_arf_band_fill
Create Date: 2026-07-01

Note: revision id kept <=32 chars — alembic_version.version_num is VARCHAR(32)
on Postgres and a longer id crashes the stamp.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_trim_discretionary"
down_revision: Union[str, Sequence[str], None] = "0031_arf_band_fill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("plans", "trim_discretionary_on_shortfall"):
        op.add_column(
            "plans",
            sa.Column(
                "trim_discretionary_on_shortfall",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    op.drop_column("plans", "trim_discretionary_on_shortfall")
