"""0031 person arf_band_fill flag

Adds people.arf_band_fill — tax-optimal ARF decumulation: draw the ARF up to
the top of the standard-rate band each year instead of just the statutory
minimum. Default False leaves existing plans unchanged.

Revision ID: 0031_arf_band_fill
Revises: 0030_rental_income
Create Date: 2026-07-01

Note: revision id kept <=32 chars — alembic_version.version_num is VARCHAR(32)
on Postgres and a longer id crashes the stamp.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_arf_band_fill"
down_revision: Union[str, Sequence[str], None] = "0030_rental_income"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("people", "arf_band_fill"):
        op.add_column(
            "people",
            sa.Column("arf_band_fill", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_column("people", "arf_band_fill")
