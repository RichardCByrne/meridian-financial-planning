"""0029 db_pensions table

Defined-benefit / final-salary pension promises (one per person): guaranteed
annual income from normal_retirement_age = accrual_rate × service_years ×
final_salary, indexed by revaluation_rate, with an optional tax-free lump sum.

Revision ID: 0029_db_pensions
Revises: 0028_merge_heads
Create Date: 2026-07-01

Note: revision id kept <=32 chars — alembic_version.version_num is VARCHAR(32)
on Postgres and a longer id crashes the stamp.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_db_pensions"
down_revision: Union[str, Sequence[str], None] = "0028_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return table in insp.get_table_names()


def upgrade() -> None:
    # Idempotent: lightweight create_all may have added this on the dev path
    # while alembic_version trails this revision.
    if not _has_table("db_pensions"):
        op.create_table(
            "db_pensions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "plan_id",
                sa.Integer(),
                sa.ForeignKey("plans.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "person_id",
                sa.Integer(),
                sa.ForeignKey("people.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("accrual_rate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("service_years", sa.Float(), nullable=False, server_default="0"),
            sa.Column("final_salary", sa.Float(), nullable=False, server_default="0"),
            sa.Column("revaluation_rate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("normal_retirement_age", sa.Integer(), nullable=False, server_default="65"),
            sa.Column("tax_free_lump_sum", sa.Float(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    if _has_table("db_pensions"):
        op.drop_table("db_pensions")
