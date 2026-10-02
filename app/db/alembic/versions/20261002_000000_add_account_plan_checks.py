"""Add bounded priority plan checks without changing historical account data."""

import sqlalchemy as sa
from alembic import op

revision = "20261002_000000_add_account_plan_checks"
down_revision = "20260929_000000_add_source_websocket"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_plan_checks",
        sa.Column("account_id", sa.String(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("generation", sa.String(32), nullable=False),
        sa.Column("credential_fingerprint", sa.String(64), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("rejected_model", sa.String(), nullable=True),
    )
    op.create_index("ix_account_plan_checks_due", "account_plan_checks", ["completed", "next_attempt_at"])


def downgrade() -> None:
    op.drop_table("account_plan_checks")
