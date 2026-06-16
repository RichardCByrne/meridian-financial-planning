"""0016 merge pension_option and onboarding_complete heads

Two 0015 revisions were created in parallel off d0e1f2a3b4c5 and both reached
main via separate PRs, leaving Alembic with two heads:
- e1f2a3b4c5d6 (people.pension_option + annuity_rate)
- f2a3b4c5d6e7 (plans.onboarding_complete)

With two heads, `alembic upgrade head` is ambiguous and aborts — which crashed
the Cloud Run container on startup (exit 255, never bound the port). This is a
no-op merge revision that joins both into a single head so `upgrade head` works.

Revision ID: bb3ec9027b80
Revises: e1f2a3b4c5d6, f2a3b4c5d6e7
Create Date: 2026-06-16 16:07:38.612961

"""
from typing import Sequence, Union

revision: str = "bb3ec9027b80"
down_revision: Union[str, Sequence[str], None] = ("e1f2a3b4c5d6", "f2a3b4c5d6e7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
