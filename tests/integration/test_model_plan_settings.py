from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update

import app.core.auth.dependencies as auth_dependencies
from app.core.auth.dashboard_access import guest_principal
from app.core.auth.dependencies import validate_dashboard_session
from app.core.clients.proxy import ProxyResponseError
from app.core.config.settings_cache import get_settings_cache
from app.db.models import DashboardSettings
from app.db.session import SessionLocal
from app.modules.proxy import model_admission
from tests.integration.test_settings_audit_changed_fields import _wait_for_settings_changed_audit_log

pytestmark = pytest.mark.integration


async def test_model_plan_settings_round_trip_preserve_clear_and_version(async_client):
    initial = (await async_client.get("/api/settings")).json()
    assert initial["modelPlanRoutingPolicies"] == {}
    # Unknown-to-catalog exact IDs are intentional, not entitlement grants.
    policy = {"future-native-model": ["pro", "prolite"], "gpt-6-luna": ["free"]}
    response = await async_client.put(
        "/api/settings",
        json={
            "expectedVersion": initial["version"],
            "modelPlanRoutingPolicies": {"future-native-model": ["PRO", "prolite", "pro"], "gpt-6-luna": [" Free "]},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["modelPlanRoutingPolicies"] == policy
    assert response.json()["version"] > initial["version"]
    audit = await _wait_for_settings_changed_audit_log()
    assert audit.details is not None
    assert "model_plan_routing_policies" in json.loads(audit.details)["changed_fields"]
    async with SessionLocal() as session:
        row = await session.get(DashboardSettings, 1)
        assert row is not None
        assert json.loads(row.model_plan_routing_policies_json) == policy
    assert json.loads((await get_settings_cache().get()).model_plan_routing_policies_json) == policy
    stale = await async_client.put(
        "/api/settings", json={"expectedVersion": initial["version"], "modelPlanRoutingPolicies": {}}
    )
    assert stale.status_code == 409
    for partial in ({"prohibitFastMode": True}, {"modelPlanRoutingPolicies": None}):
        preserved = await async_client.put("/api/settings", json=partial)
        assert preserved.status_code == 200, preserved.text
        assert preserved.json()["modelPlanRoutingPolicies"] == policy
    cleared = await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": {}})
    assert cleared.status_code == 200
    assert cleared.json()["modelPlanRoutingPolicies"] == {}
    assert (await async_client.get("/api/settings")).json()["modelPlanRoutingPolicies"] == {}
    assert (await get_settings_cache().get()).model_plan_routing_policies_json == "{}"


@pytest.mark.parametrize(
    "invalid",
    [
        {"": ["free"]},
        {"gpt 6": ["free"]},
        {" gpt-6": ["free"]},
        {"gpt-6": []},
        {"gpt-6": ["guest"]},
        {"gpt-6": [1]},
        {"gpt-6": "free"},
        [],
        "{}",
    ],
)
async def test_model_plan_settings_invalid_update_is_atomic(async_client, invalid):
    policy = {"gpt-6-luna": ["free"]}
    saved = await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": policy})
    assert saved.status_code == 200
    invalid_response = await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": invalid})
    assert invalid_response.status_code == 422, invalid_response.text
    current = (await async_client.get("/api/settings")).json()
    assert current["modelPlanRoutingPolicies"] == policy
    assert current["version"] == saved.json()["version"]


async def test_model_plan_settings_guest_cannot_write(async_client, app_instance, monkeypatch):
    app_instance.dependency_overrides[validate_dashboard_session] = guest_principal
    monkeypatch.setattr(auth_dependencies, "validate_dashboard_session", AsyncMock(return_value=guest_principal()))
    try:
        response = await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": {"gpt-6-luna": ["free"]}})
        assert response.status_code == 403, response.text
    finally:
        app_instance.dependency_overrides.pop(validate_dashboard_session, None)
    assert (await async_client.get("/api/settings")).json()["modelPlanRoutingPolicies"] == {}


@pytest.mark.parametrize(
    ("stored", "readable"),
    [
        ("private invalid json", {}),
        # A manual edit or a plan later removed from the vocabulary.
        (json.dumps({"gpt-6-luna": ["free"], "retired-model": ["retired-plan"]}), {"gpt-6-luna": ["free"]}),
    ],
)
async def test_model_plan_settings_invalid_stored_mapping_is_readable_and_repairable(async_client, stored, readable):
    async with SessionLocal() as session:
        await session.execute(update(DashboardSettings).values(model_plan_routing_policies_json=stored))
        await session.commit()
    await get_settings_cache().invalidate()
    with pytest.raises(ProxyResponseError):
        await model_admission.routing_policy_snapshot()
    current = await async_client.get("/api/settings")
    assert current.status_code == 200, current.text
    assert current.json()["modelPlanRoutingPolicies"] == readable
    repaired = await async_client.put(
        "/api/settings", json={"expectedVersion": current.json()["version"], "modelPlanRoutingPolicies": {}}
    )
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["modelPlanRoutingPolicies"] == {}
    async with SessionLocal() as session:
        row = await session.get(DashboardSettings, 1)
        assert row is not None
        assert row.model_plan_routing_policies_json == "{}"
    assert (await model_admission.routing_policy_snapshot())[1] == {}
