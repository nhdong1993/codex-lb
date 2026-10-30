"""add lifetime api key limit window enum value

Revision ID: 20261027_000000_add_lifetime_api_key_limit_window
Revises: 20261011_020000_add_model_plan_routing_policies
Create Date: 2026-10-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "20261027_000000_add_lifetime_api_key_limit_window"
down_revision = "20261011_020000_add_model_plan_routing_policies"
branch_labels = None
depends_on = None


def _table_exists(connection: Connection, table_name: str) -> bool:
    inspector = sa.inspect(connection)
    return inspector.has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "api_key_limits"):
        return
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("ALTER TYPE limit_window ADD VALUE IF NOT EXISTS 'lifetime'"))


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "api_key_limits"):
        return
    if bind.dialect.name != "postgresql":
        return
    # PostgreSQL enum values cannot be removed safely in-place here.
    return
