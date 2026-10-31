"""Add accounts.reserved_api_key_id.

Revision ID: 20261031_000000_add_account_reserved_api_key
Revises: 20261027_000000_add_lifetime_api_key_limit_window
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261031_000000_add_account_reserved_api_key"
down_revision = "20261027_000000_add_lifetime_api_key_limit_window"
branch_labels = None
depends_on = None

_COLUMN = "reserved_api_key_id"
_FK_NAME = "fk_accounts_reserved_api_key_id"
_INDEX_NAME = "ix_accounts_reserved_api_key_id"


def _columns(bind: sa.engine.Connection) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns("accounts")}


def _indexes(bind: sa.engine.Connection) -> set[str]:
    return {str(index["name"]) for index in sa.inspect(bind).get_indexes("accounts")}


def _reserved_fk_names(bind: sa.engine.Connection) -> list[str]:
    return [
        str(fk["name"])
        for fk in sa.inspect(bind).get_foreign_keys("accounts")
        if fk.get("name") and fk.get("referred_table") == "api_keys" and _COLUMN in fk.get("constrained_columns", ())
    ]


def upgrade() -> None:
    bind = op.get_bind()
    if _COLUMN not in _columns(bind):
        with op.batch_alter_table("accounts") as batch_op:
            batch_op.add_column(sa.Column(_COLUMN, sa.String(), nullable=True))
            batch_op.create_foreign_key(_FK_NAME, "api_keys", [_COLUMN], ["id"], ondelete="SET NULL")
    if _INDEX_NAME not in _indexes(bind):
        op.create_index(_INDEX_NAME, "accounts", [_COLUMN])


def downgrade() -> None:
    bind = op.get_bind()
    if _INDEX_NAME in _indexes(bind):
        op.drop_index(_INDEX_NAME, table_name="accounts")
    if _COLUMN in _columns(bind):
        fk_names = _reserved_fk_names(bind)
        with op.batch_alter_table("accounts") as batch_op:
            for fk_name in fk_names:
                batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.drop_column(_COLUMN)
