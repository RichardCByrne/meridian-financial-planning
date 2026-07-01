"""0026 protection: person death_year + life_policies table

Adds:
- people.death_year — optional planned/what-if death year (protection & survivor
  modelling). NULL = die at life_expectancy as before.
- life_policies — term-life protection policies (insured person, sum assured,
  annual premium, cover term). Premiums drain cash while in force; the sum
  assured pays out tax-free to survivors if the insured dies within the term.

Revision ID: 0026_protection
Revises: 0025_drop_legacy_exp_cat
Create Date: 2026-07-01

Note: revision id kept <=32 chars — alembic_version.version_num is VARCHAR(32)
on Postgres and a longer id crashes the stamp.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_protection"
down_revision: Union[str, Sequence[str], None] = "0025_drop_legacy_exp_cat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def _has_table(table: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return table in insp.get_table_names()


def upgrade() -> None:
    # Idempotent: lightweight create_all may have added these on the dev path
    # while alembic_version trails this revision.
    if not _has_column("people", "death_year"):
        op.add_column("people", sa.Column("death_year", sa.Integer(), nullable=True))

    if not _has_table("life_policies"):
        op.create_table(
            "life_policies",
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
            sa.Column("kind", sa.String(length=40), nullable=False, server_default="term_life"),
            sa.Column("sum_assured", sa.Float(), nullable=False, server_default="0"),
            sa.Column("premium_annual", sa.Float(), nullable=False, server_default="0"),
            sa.Column("start_year", sa.Integer(), nullable=False),
            sa.Column("end_year", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    if _has_table("life_policies"):
        op.drop_table("life_policies")
    if _has_column("people", "death_year"):
        op.drop_column("people", "death_year")
