import pytest

from tests.integration import test_model_source_pool as pool_fixtures
from tests.integration.test_source_reference_scope_gaps import _set_model

make_pool = pool_fixtures.make_pool
pool_clock = pool_fixtures.pool_clock
pytestmark = pytest.mark.integration


async def test_subscription_plan_policy_does_not_restrict_same_slug_source(async_client, make_pool):
    model = "gpt-6-luna"
    pool = await make_pool(1)
    await _set_model(async_client, pool.ids[0], model, "source-native-name")
    key = await async_client.patch(f"/api/api-keys/{pool.key_id}", json={"allowedModels": [model]})
    assert key.status_code == 200, key.text
    saved = await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": {model: ["free"]}})
    assert saved.status_code == 200
    # No subscription accounts exist. Source scope, not the spelling of the
    # model, selects this dispatch domain; the subscription restriction is inert.
    for path in ("/v1/responses", "/backend-api/codex/responses/"):
        response = await async_client.post(
            path, headers=pool.headers, json={"model": model, "input": "hello", "stream": True}
        )
        assert response.status_code == 200, response.text
        assert "response.completed" in response.text
    assert len(pool.calls) == 2
    assert all(name == "pool-0" and body["model"] == "source-native-name" for name, body in pool.calls)
