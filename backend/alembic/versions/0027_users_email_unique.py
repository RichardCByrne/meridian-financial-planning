"""0027 unique index on users.email

Enforce one account per email address. A second Firebase provider for the same
verified email now links to the existing `users` row (see auth._link_existing)
instead of silently creating a duplicate account with a separate data silo.

Nullable email is fine: both SQLite and Postgres treat NULLs as distinct under
a unique index, so email-less rows (e.g. phone auth) are unaffected.

If a pre-existing database already holds duplicate non-null emails, this index
creation will fail — dedupe those rows first. In practice the app is small and
email was previously only ever set from Firebase identities.

Revision ID: 0027_users_email_unique
Revises: 0026_asset_charge
Create Date: 2026-07-01

Note: revision id kept <=32 chars because Alembic's
``alembic_version.version_num`` column is ``VARCHAR(32)`` on Postgres.

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0027_users_email_unique"
down_revision: Union[str, Sequence[str], None] = "0026_asset_charge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
