from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import _build_alembic_config, check_schema_drift, run_upgrade

pytestmark = pytest.mark.integration

PARENT = "20260910_010000_merge_beta6_and_key_groups"
HEAD = "20261002_010000_add_credential_generation"


def test_reset_credit_migration_preserves_legacy_pins(tmp_path: Path) -> None:
    url = os.environ.get(
        "CODEX_LB_TEST_MIGRATION_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'reset-outcomes.db'}"
    )
    run_upgrade(url, PARENT, bootstrap_legacy=False)
    engine = create_engine(url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg"))
    try:
        with engine.begin() as connection:
            connection.execute(
                # Seed the historical schema independently of current ORM
                # defaults, which include columns added by later revisions.
                text(
                    "INSERT INTO accounts (id, email, plan_type, access_token_encrypted, refresh_token_encrypted, "
                    "id_token_encrypted, last_refresh, status, codex_installation_id) VALUES "
                    "('historical', 'migration@example.com', 'plus', :token, :token, :token, "
                    "'2026-09-21 00:00:00', 'active', 'historical-installation')"
                ),
                {"token": b"test"},
            )
            connection.execute(
                text(
                    "INSERT INTO reset_credit_redeem_requests "
                    "(account_id, redeem_request_id, credit_id, created_at) "
                    "VALUES ('historical', 'request', 'original', '2026-09-21 00:00:00')"
                )
            )
        run_upgrade(url, "head", bootstrap_legacy=False)
        assert ScriptDirectory.from_config(_build_alembic_config(url)).get_heads() == [HEAD]
        assert check_schema_drift(url) == ()
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT credit_id, outcome, origin, attempt_count, usage_verified FROM reset_credit_redeem_requests"
                )
            ).one()
            assert tuple(row) == ("original", "unknown", "legacy", 0, False)
        command.downgrade(_build_alembic_config(url), PARENT)
        assert "outcome" not in {c["name"] for c in inspect(engine).get_columns("reset_credit_redeem_requests")}
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT credit_id FROM reset_credit_redeem_requests")).scalar_one()
                == "original"
            )
        run_upgrade(url, "head", bootstrap_legacy=False)
        assert check_schema_drift(url) == ()
    finally:
        engine.dispose()
