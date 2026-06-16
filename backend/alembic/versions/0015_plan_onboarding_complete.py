"""0015 plan onboarding_complete

Adds:
- ``plans.onboarding_complete`` (bool, not null, default false): set true the
  first time a plan has people + income + assets, so the UI can skip the
  first-run getting-started stepper without recomputing completion on every load.

Revision ID: f2a3b4c5d6e7
Revises: d0e1f2a3b4c5
Create Date: 2026-06-16 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "onboarding_complete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.drop_column("onboarding_complete")
