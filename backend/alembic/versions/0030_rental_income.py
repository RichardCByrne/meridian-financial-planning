"""0030 rental income tax fields

Adds to income_sources (rental income only):
- rental_expenses_pct — allowable expenses as a fraction of gross rent.
- furnishings_value — basis for the wear-and-tear capital allowance.
Taxable rental profit = gross − gross×rental_expenses_pct − wear_and_tear.

Revision ID: 0030_rental_income
Revises: 0029_db_pensions
Create Date: 2026-07-01

Note: revision id kept <=32 chars — alembic_version.version_num is VARCHAR(32)
on Postgres and a longer id crashes the stamp.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030_rental_income"
down_revision: Union[str, Sequence[str], None] = "0029_db_pensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    # Idempotent: lightweight create_all/ALTER may have added these on the dev
    # path while alembic_version trails this revision.
    if not _has_column("income_sources", "rental_expenses_pct"):
        op.add_column(
            "income_sources",
            sa.Column("rental_expenses_pct", sa.Float(), nullable=False, server_default="0"),
        )
    if not _has_column("income_sources", "furnishings_value"):
        op.add_column(
            "income_sources",
            sa.Column("furnishings_value", sa.Float(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("income_sources", "furnishings_value")
    op.drop_column("income_sources", "rental_expenses_pct")
