"""Distinguish credential replacement from routine OAuth rotation."""

import sqlalchemy as sa
from alembic import op

revision = "20261002_010000_add_credential_generation"
down_revision = "20261002_000000_add_account_plan_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts", sa.Column("credential_generation", sa.Integer(), nullable=False, server_default=sa.text("0"))
    )


def downgrade() -> None:
    op.drop_column("accounts", "credential_generation")
