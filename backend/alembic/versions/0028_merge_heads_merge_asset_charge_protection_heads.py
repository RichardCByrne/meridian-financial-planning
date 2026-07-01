"""merge asset_charge + protection heads

Two feature branches both revised from 0025, creating parallel Alembic heads:
  0025 → 0026_asset_charge → 0027_users_email_unique   (fund charges + email)
  0025 → 0026_protection                                (death + life policies)

`alembic upgrade head` refuses to run with multiple heads, which would break the
Dockerfile entrypoint in production. This empty merge revision rejoins them into
a single head; no schema change of its own.

Revision ID: 0028_merge_heads
Revises: 0026_protection, 0027_users_email_unique
Create Date: 2026-07-01

Note: revision id kept <=32 chars — alembic_version.version_num is VARCHAR(32)
on Postgres and a longer id crashes the stamp.

"""
from typing import Sequence, Union

revision: str = "0028_merge_heads"
down_revision: Union[str, Sequence[str], None] = ("0026_protection", "0027_users_email_unique")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
