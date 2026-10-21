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


async def test_same_slug_source_keeps_a_tier_the_native_model_would_drop(async_client, make_pool):
    from dataclasses import replace

    from sqlalchemy import update

    from app.core.openai.model_registry import get_model_registry
    from app.db.models import Account
    from app.db.session import SessionLocal
    from tests.integration.test_proxy_transient_retry import _import_account

    model = "gpt-6-luna"
    pool = await make_pool(1)
    await _set_model(async_client, pool.ids[0], model, "source-native-name")
    key = await async_client.patch(f"/api/api-keys/{pool.key_id}", json={"allowedModels": [model]})
    assert key.status_code == 200, key.text
    plans = {}
    for name, plan in (("native-plus", "plus"), ("native-free", "free")):
        account_id = await _import_account(async_client, name, f"{name}@example.com")
        plans[account_id] = plan
        async with SessionLocal() as session:
            await session.execute(update(Account).where(Account.id == account_id).values(plan_type=plan))
            await session.commit()
    # Catalog evidence under which the native model would lose its tier.
    registry = get_model_registry()
    base = registry.get_models_with_fallback()[model]
    raw = {key: value for key, value in base.raw.items() if key not in {"service_tiers", "additional_speed_tiers"}}
    plus = replace(base, raw={**raw, "service_tiers": [{"id": "priority", "name": "Fast"}]})
    free = replace(base, raw=raw)
    await registry.update(
        {"plus": [plus], "free": [free]},
        per_account_results={
            account_id: (plan, [plus] if plan == "plus" else [free]) for account_id, plan in plans.items()
        },
        active_account_plans=plans,
    )
    saved = await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": {model: ["free"]}})
    assert saved.status_code == 200
    response = await async_client.post(
        "/v1/responses",
        headers=pool.headers,
        json={"model": model, "input": "hello", "stream": True, "service_tier": "priority"},
    )
    assert response.status_code == 200, response.text
    assert "response.completed" in response.text
    assert [name for name, _ in pool.calls] == ["pool-0"]
    assert pool.calls[0][1]["service_tier"] == "priority"
