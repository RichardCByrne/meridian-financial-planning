"""0025 fold the redundant "legacy" expense category into "discretionary"

basic / discretionary / legacy were all financially identical recurring
expenses — only single_year (one-off) behaves differently. "legacy" carried no
distinct engine behaviour and was barely explained, so collapse it into
"discretionary". (The Legacy *tab* — bequests/estate — is unrelated and
unchanged.)

Idempotent: re-running is a no-op once rows are migrated.

Revision ID: 0025_drop_legacy_expense_category
Revises: 0024_consolidate_goal_kinds
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0025_drop_legacy_expense_category"
down_revision: Union[str, Sequence[str], None] = "0024_consolidate_goal_kinds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE expenses SET category = 'discretionary' WHERE category = 'legacy'")


def downgrade() -> None:
    # One-way: the original legacy rows aren't distinguishable after the merge.
    pass
