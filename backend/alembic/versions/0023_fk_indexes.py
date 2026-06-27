"""0023 indexes on frequently-filtered foreign-key columns

SQLAlchemy/Alembic don't auto-index foreign-key columns, but nearly every
read filters by one: per-resource lists and the projection's eager-loads
filter by ``plan_id``; income lookups by ``person_id``; liability adjustments
by ``liability_id``; and ``list_plans`` joins ``plan_members`` on ``user_id``
(not covered by the (plan_id, user_id) PK's leading column). Without these,
Postgres sequentially scans the table. Add covering single-column indexes.

(``plan_invites.token`` and ``assumptions.plan_id`` are already indexed via
their UNIQUE constraints, so they're omitted here.)

Revision ID: 0023_fk_indexes
Revises: 0022_child_costs
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0023_fk_indexes"
down_revision: Union[str, Sequence[str], None] = "0022_child_costs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (index_name, table, column)
_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_people_plan_id", "people", "plan_id"),
    ("ix_income_sources_person_id", "income_sources", "person_id"),
    ("ix_expenses_plan_id", "expenses", "plan_id"),
    ("ix_assets_plan_id", "assets", "plan_id"),
    ("ix_liabilities_plan_id", "liabilities", "plan_id"),
    ("ix_liability_adjustments_liability_id", "liability_adjustments", "liability_id"),
    ("ix_goals_plan_id", "goals", "plan_id"),
    ("ix_scenarios_plan_id", "scenarios", "plan_id"),
    ("ix_bequests_plan_id", "bequests", "plan_id"),
    ("ix_benefits_plan_id", "benefits", "plan_id"),
    ("ix_children_plan_id", "children", "plan_id"),
    ("ix_plan_invites_plan_id", "plan_invites", "plan_id"),
    ("ix_plan_members_user_id", "plan_members", "user_id"),
)


def upgrade() -> None:
    for name, table, column in _INDEXES:
        op.create_index(name, table, [column])


def downgrade() -> None:
    for name, table, _column in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
