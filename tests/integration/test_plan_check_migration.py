import os
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import _build_alembic_config, check_schema_drift, run_upgrade

pytestmark = pytest.mark.integration
PARENT = "20260929_000000_add_source_websocket"
REVISION = "20261002_010000_add_credential_generation"


def test_plan_check_upgrade_preserves_credentials_and_round_trips(tmp_path: Path):
    url = os.environ.get("CODEX_LB_TEST_MIGRATION_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'checks.db'}")
    config = _build_alembic_config(url)
    assert ScriptDirectory.from_config(config).get_heads() == [REVISION]
    run_upgrade(url, PARENT, bootstrap_legacy=False)
    engine = create_engine(url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg"))
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO accounts (id,email,plan_type,status,access_token_encrypted,refresh_token_encrypted,"
                    "id_token_encrypted,last_refresh,codex_installation_id) VALUES "
                    "('historical','old@example.com','plus','active',:a,:r,:i,'2026-09-30','installation')"
                ),
                {"a": b"access", "r": b"refresh", "i": b"id"},
            )
        run_upgrade(url, "head", bootstrap_legacy=False)
        assert check_schema_drift(url) == ()
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM account_plan_checks")) == 0
            assert conn.scalar(text("SELECT credential_generation FROM accounts WHERE id='historical'")) == 0
            assert conn.execute(
                text(
                    "SELECT plan_type,status,access_token_encrypted,refresh_token_encrypted,id_token_encrypted "
                    "FROM accounts WHERE id='historical'"
                )
            ).one() == ("plus", "active", b"access", b"refresh", b"id")
        command.downgrade(config, "20261002_000000_add_account_plan_checks")
        assert "credential_generation" not in {column["name"] for column in inspect(engine).get_columns("accounts")}
        run_upgrade(url, "head", bootstrap_legacy=False)
        assert check_schema_drift(url) == ()
        command.downgrade(config, PARENT)
        assert not inspect(engine).has_table("account_plan_checks")
        run_upgrade(url, "head", bootstrap_legacy=False)
        assert check_schema_drift(url) == ()
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT refresh_token_encrypted FROM accounts WHERE id='historical'")) == b"refresh"
    finally:
        engine.dispose()
