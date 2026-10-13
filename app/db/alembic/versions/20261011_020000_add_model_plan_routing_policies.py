"""Persist opt-in subscription model plan restrictions without changing existing routing."""

import sqlalchemy as sa
from alembic import op

revision = "20261011_020000_add_model_plan_routing_policies"
down_revision = "20261002_010000_add_credential_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dashboard_settings",
        sa.Column("model_plan_routing_policies_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("dashboard_settings", "model_plan_routing_policies_json")
