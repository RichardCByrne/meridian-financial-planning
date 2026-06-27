"""0025 fold the redundant "legacy" expense category into "discretionary"

basic / discretionary / legacy were all financially identical recurring
expenses — only single_year (one-off) behaves differently. "legacy" carried no
distinct engine behaviour and was barely explained, so collapse it into
"discretionary". (The Legacy *tab* — bequests/estate — is unrelated and
unchanged.)

Idempotent: re-running is a no-op once rows are migrated.

Revision ID: 0025_drop_legacy_exp_cat
Revises: 0024_consolidate_goal_kinds
Create Date: 2026-06-27

Note: the revision id is kept <=32 chars because Alembic's
``alembic_version.version_num`` column is ``VARCHAR(32)`` on Postgres — a
longer id raises StringDataRightTruncation when the version is stamped.

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0025_drop_legacy_exp_cat"
down_revision: Union[str, Sequence[str], None] = "0024_consolidate_goal_kinds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE expenses SET category = 'discretionary' WHERE category = 'legacy'")


def downgrade() -> None:
    # One-way: the original legacy rows aren't distinguishable after the merge.
    pass
