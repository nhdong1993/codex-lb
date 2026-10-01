from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import _build_alembic_config, check_schema_drift, run_upgrade

pytestmark = pytest.mark.integration
PARENT = "20260926_010000_add_source_ownership_history"
REVISION = "20260928_000000_add_account_subscription_snapshot"
COLUMNS = {
    "subscription_active_until",
    "subscription_checked_at",
    "subscription_fingerprint",
    "subscription_attempted_at",
}


def test_upgrade_preserves_existing_accounts_and_round_trips(tmp_path: Path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'subscription.db'}"
    config = _build_alembic_config(url)
    assert ScriptDirectory.from_config(config).get_heads() == ["20260929_000000_add_source_websocket"]
    run_upgrade(url, PARENT, bootstrap_legacy=False)
    engine = create_engine(url.replace("+aiosqlite", ""))
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO accounts (id, email, plan_type, status, access_token_encrypted, "
                    "refresh_token_encrypted, "
                    "id_token_encrypted, last_refresh, codex_installation_id) "
                    "VALUES ('legacy', 'legacy@example.com', 'plus', 'paused', :a, :r, :i, "
                    "'2026-09-01 00:00:00', 'installation')"
                ),
                {"a": b"access", "r": b"refresh", "i": b"id"},
            )
        run_upgrade(url, "head", bootstrap_legacy=False)
        assert check_schema_drift(url) == ()
        with engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM accounts WHERE id = 'legacy'")).mappings().one()
            assert all(row[column] is None for column in COLUMNS)
            assert row["status"] == "paused"
            assert row["access_token_encrypted"] == b"access"
        command.downgrade(config, PARENT)
        assert not COLUMNS.intersection(column["name"] for column in inspect(engine).get_columns("accounts"))
        run_upgrade(url, "head", bootstrap_legacy=False)
        assert check_schema_drift(url) == ()
    finally:
        engine.dispose()
