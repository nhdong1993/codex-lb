from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import _build_alembic_config, check_schema_drift, run_upgrade

pytestmark = pytest.mark.integration

PARENT = "20261002_010000_add_credential_generation"
REVISION = "20261011_020000_add_model_plan_routing_policies"
COLUMN = "model_plan_routing_policies_json"


def test_model_plan_migration_backfill_downgrade_reupgrade_and_single_head(tmp_path: Path) -> None:
    database = tmp_path / "model-plan-policy.db"
    url = f"sqlite+aiosqlite:///{database}"
    config = _build_alembic_config(url)
    assert ScriptDirectory.from_config(config).get_heads() == ["20261031_000000_add_account_reserved_api_key"]
    run_upgrade(url, PARENT, bootstrap_legacy=False)
    engine = create_engine(f"sqlite:///{database}")
    try:
        with engine.begin() as connection:
            connection.execute(text("UPDATE dashboard_settings SET prohibit_fast_mode = 1 WHERE id = 1"))
        run_upgrade(url, "head", bootstrap_legacy=False)
        with engine.begin() as connection:
            assert connection.execute(text(f"SELECT {COLUMN} FROM dashboard_settings")).scalar_one() == "{}"
            connection.execute(
                text(f"UPDATE dashboard_settings SET {COLUMN} = :policy"), {"policy": '{"gpt-6-luna":["free"]}'}
            )
        # Re-running an upgrade must never seed/clear an operator's policy.
        run_upgrade(url, "head", bootstrap_legacy=False)
        with engine.connect() as connection:
            assert (
                connection.execute(text(f"SELECT {COLUMN} FROM dashboard_settings")).scalar_one()
                == '{"gpt-6-luna":["free"]}'
            )
        command.downgrade(config, PARENT)
        with engine.connect() as connection:
            assert COLUMN not in {column["name"] for column in inspect(connection).get_columns("dashboard_settings")}
            assert connection.execute(text("SELECT prohibit_fast_mode FROM dashboard_settings")).scalar_one() == 1
        run_upgrade(url, "head", bootstrap_legacy=False)
        with engine.connect() as connection:
            assert connection.execute(text(f"SELECT {COLUMN} FROM dashboard_settings")).scalar_one() == "{}"
            assert connection.execute(text("SELECT prohibit_fast_mode FROM dashboard_settings")).scalar_one() == 1
        assert check_schema_drift(url) == ()
    finally:
        engine.dispose()
