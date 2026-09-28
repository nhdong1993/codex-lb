"""Persist shared subscription snapshots without inferring historical deadlines."""

import sqlalchemy as sa
from alembic import op

revision = "20260928_000000_add_account_subscription_snapshot"
down_revision = "20260926_010000_add_source_ownership_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("subscription_active_until", sa.DateTime(), nullable=True))
    op.add_column("accounts", sa.Column("subscription_checked_at", sa.DateTime(), nullable=True))
    op.add_column("accounts", sa.Column("subscription_fingerprint", sa.String(64), nullable=True))
    op.add_column("accounts", sa.Column("subscription_attempted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for name in (
        "subscription_attempted_at",
        "subscription_fingerprint",
        "subscription_checked_at",
        "subscription_active_until",
    ):
        op.drop_column("accounts", name)
