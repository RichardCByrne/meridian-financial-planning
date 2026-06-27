"""0022 per-child rearing-cost columns

Adds age-gated rearing-cost columns to the ``children`` table: childcare,
primary, secondary (public) and a private-fee top-up plus an everyday
(food/clothes) line. The simulator age-gates each against the child's dob
using TaxConfig stage boundaries and escalates by the plan inflation rate.
Third-level/college is modelled via an ``education`` goal, not here.

Revision ID: 0022_child_costs
Revises: 0021_benefits
Create Date: 2026-06-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_child_costs"
down_revision: Union[str, Sequence[str], None] = "0021_benefits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    # Idempotent: lightweight create_all may have added these already while
    # alembic_version trails this revision.
    if not _has_column("children", "childcare_annual"):
        op.add_column(
            "children",
            sa.Column("childcare_annual", sa.Float(), nullable=False, server_default="0"),
        )
    if not _has_column("children", "primary_annual"):
        op.add_column(
            "children",
            sa.Column("primary_annual", sa.Float(), nullable=False, server_default="0"),
        )
    if not _has_column("children", "secondary_annual"):
        op.add_column(
            "children",
            sa.Column("secondary_annual", sa.Float(), nullable=False, server_default="0"),
        )
    if not _has_column("children", "secondary_is_private"):
        op.add_column(
            "children",
            sa.Column(
                "secondary_is_private", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )
    if not _has_column("children", "secondary_private_fee_annual"):
        op.add_column(
            "children",
            sa.Column(
                "secondary_private_fee_annual", sa.Float(), nullable=False, server_default="0"
            ),
        )
    if not _has_column("children", "everyday_annual"):
        op.add_column(
            "children",
            sa.Column("everyday_annual", sa.Float(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("children", "everyday_annual")
    op.drop_column("children", "secondary_private_fee_annual")
    op.drop_column("children", "secondary_is_private")
    op.drop_column("children", "secondary_annual")
    op.drop_column("children", "primary_annual")
    op.drop_column("children", "childcare_annual")
