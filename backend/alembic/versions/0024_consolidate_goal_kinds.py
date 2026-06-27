"""0024 consolidate one-off-spend goal kinds into a single "spend" kind

milestone / education / gift / pre_retirement_spend were all financially
identical — each injects a one-off cost in the target year, graded
achieved/missed on shortfall. The distinction lived only in the goal's name.
Collapse them to a single canonical "spend" kind. net_worth (savings target)
and retirement (timeline marker) are unchanged.

Idempotent: re-running the UPDATE is a no-op once rows are migrated.

Revision ID: 0024_consolidate_goal_kinds
Revises: 0023_fk_indexes
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0024_consolidate_goal_kinds"
down_revision: Union[str, Sequence[str], None] = "0023_fk_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY = ("milestone", "education", "gift", "pre_retirement_spend")


def upgrade() -> None:
    legacy = ", ".join(f"'{k}'" for k in _LEGACY)
    op.execute(f"UPDATE goals SET kind = 'spend' WHERE kind IN ({legacy})")


def downgrade() -> None:
    # One-way: the original sub-type per row isn't recoverable. Map every
    # consolidated spend back to the historical default ("milestone").
    op.execute("UPDATE goals SET kind = 'milestone' WHERE kind = 'spend'")
