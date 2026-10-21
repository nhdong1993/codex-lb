from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update

import app.modules.proxy.service as proxy_module
from app.core.cache.invalidation import NAMESPACE_SETTINGS, CacheInvalidationPoller
from app.core.clients.proxy import ProxyResponseError
from app.core.config.settings_cache import SettingsCache, get_settings_cache
from app.core.errors import openai_error
from app.core.openai.models import CompactResponsePayload
from app.db.models import Account, AccountStatus, DashboardSettings
from app.db.session import SessionLocal
from app.dependencies import get_proxy_service_for_app
from app.modules.proxy import model_admission
from app.modules.proxy.account_cache import AccountSelectionCache, get_account_selection_cache
from tests.integration.test_proxy_transient_retry import _import_account, _success_sse_event

pytestmark = pytest.mark.integration
MODELS = ("gpt-5.6-terra", "gpt-5.6-luna", "gpt-6-luna")
POLICY = {model: ["free"] for model in MODELS}


@pytest.fixture
async def native_pool(async_client, app_instance, monkeypatch):
    accounts = {}
    for name, plan in (("paid", "plus"), ("free-a", "free"), ("free-b", "free")):
        account_id = await _import_account(async_client, name, f"{name}@example.com")
        accounts[name] = account_id
        async with SessionLocal() as session:
            await session.execute(update(Account).where(Account.id == account_id).values(plan_type=plan))
            await session.commit()
    saved = await async_client.put(
        "/api/settings",
        json={
            "modelPlanRoutingPolicies": POLICY,
            "routingStrategy": "usage_weighted",
            "proxyRequestBudgetSeconds": 15,
            "compactRequestBudgetSeconds": 15,
        },
    )
    assert saved.status_code == 200, saved.text
    service = get_proxy_service_for_app(app_instance)
    # Pytest normally disables this cache. Keep it genuinely enabled for these requests.
    service._load_balancer._selection_inputs_cache = AccountSelectionCache(ttl_seconds=60)
    seen = []

    async def stream(payload, headers, access_token, account_id, **kwargs):
        seen.append(account_id)
        yield _success_sse_event()

    async def compact(payload, headers, access_token, account_id):
        seen.append(account_id)
        return CompactResponsePayload.model_validate({"object": "response.compaction", "output": []})

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(proxy_module, "core_compact_responses", compact)
    return accounts, seen, service


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
async def test_model_plan_native_public_selection(async_client, native_pool, model, path):
    _, seen, _ = native_pool
    response = await async_client.post(path, json={"model": model, "input": "hello", "stream": True})
    assert response.status_code == 200, response.text
    assert "response.completed" in response.text
    assert len(seen) == 1 and seen[0] in {"free-a", "free-b"}


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/backend-api/codex/responses/compact"])
async def test_model_plan_other_native_surfaces(async_client, native_pool, path):
    _, seen, _ = native_pool
    payload = {"model": MODELS[0], "instructions": "hi", "input": "hello"}
    if path.endswith("completions"):
        payload = {"model": MODELS[0], "messages": [{"role": "user", "content": "hello"}], "stream": True}
    response = await async_client.post(path, json=payload)
    assert response.status_code == 200, response.text
    assert len(seen) == 1 and seen[0] in {"free-a", "free-b"}


async def test_unconfigured_native_model_retains_paid_api_key_scope(async_client, native_pool):
    accounts, seen, _ = native_pool
    assert (await async_client.put("/api/settings", json={"apiKeyAuthEnabled": True})).status_code == 200
    key = await async_client.post(
        "/api/api-keys/", json={"name": "unconfigured-paid", "assignedAccountIds": [accounts["paid"]]}
    )
    assert key.status_code == 200, key.text
    response = await async_client.post(
        "/v1/responses",
        headers={"Authorization": f"Bearer {key.json()['key']}"},
        json={"model": "gpt-5.4", "input": "hello", "stream": True},
    )
    assert response.status_code == 200, response.text
    assert "response.completed" in response.text
    assert seen == ["paid"]


@pytest.mark.parametrize("restriction", ["no-free", "paused-free", "paid-key", "single-paid", "file-owner"])
async def test_model_plan_no_paid_fallback_or_owner_move(async_client, native_pool, restriction):
    accounts, seen, service = native_pool
    headers = {}
    payload = {"model": MODELS[0], "input": "hello", "stream": True}
    if restriction in {"no-free", "paused-free"}:
        values = {"plan_type": "plus"} if restriction == "no-free" else {"status": AccountStatus.PAUSED}
        async with SessionLocal() as session:
            await session.execute(update(Account).where(Account.plan_type == "free").values(**values))
            await session.commit()
        get_account_selection_cache().invalidate()
    elif restriction == "paid-key":
        assert (await async_client.put("/api/settings", json={"apiKeyAuthEnabled": True})).status_code == 200
        key = await async_client.post(
            "/api/api-keys/", json={"name": "paid-only", "assignedAccountIds": [accounts["paid"]]}
        )
        assert key.status_code == 200
        headers = {"Authorization": f"Bearer {key.json()['key']}"}
    elif restriction == "single-paid":
        assert (
            await async_client.put(
                "/api/settings", json={"singleAccountId": accounts["paid"], "routingStrategy": "single_account"}
            )
        ).status_code == 200
    else:
        await service._pin_file_account("file-paid-owner", accounts["paid"])
        payload["input"] = [{"role": "user", "content": [{"type": "input_file", "file_id": "file-paid-owner"}]}]
    response = await async_client.post("/v1/responses", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert not seen, response.text
    assert "response.failed" in response.text
    assert "response.completed" not in response.text
    if restriction == "file-owner":
        assert '"code":"no_accounts"' in response.text, response.text


async def test_model_plan_policy_fingerprint_and_clear_with_live_selection_ttl(async_client, native_pool, monkeypatch):
    accounts, _, service = native_pool
    balancer = service._load_balancer
    peer_settings = SettingsCache(ttl_seconds=60)
    peer_poller = CacheInvalidationPoller(SessionLocal)
    peer_poller.on_invalidation(NAMESPACE_SETTINGS, lambda: peer_settings.invalidate(propagate=False))
    await peer_poller._poll_once()
    monkeypatch.setattr(model_admission, "get_settings_cache", lambda: peer_settings)
    # A separate selection cache models a replica whose selection invalidation
    # has not arrived: the visible settings snapshot must still distinguish it.
    before = await balancer._load_selection_inputs(model=MODELS[0])
    assert {a.id for a in before.accounts} == {accounts["free-a"], accounts["free-b"]}
    assert {a.id for a in before.continuity_owner_candidates} == set(accounts.values())
    assert (
        await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": {MODELS[0]: ["plus"]}})
    ).status_code == 200
    stale = await balancer._load_selection_inputs(model=MODELS[0])
    assert {a.id for a in stale.accounts} == {accounts["free-a"], accounts["free-b"]}
    await peer_poller._poll_once()
    after = await balancer._load_selection_inputs(model=MODELS[0])
    assert {a.id for a in after.accounts} == {accounts["paid"]}
    unconfigured = await balancer._load_selection_inputs(model=MODELS[1])
    assert {a.id for a in unconfigured.accounts} == set(accounts.values())
    assert (await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": {}})).status_code == 200
    await peer_poller._poll_once()
    cleared = await balancer._load_selection_inputs(model=MODELS[0])
    assert {a.id for a in cleared.accounts} == set(accounts.values())


async def test_model_plan_current_account_plan_overrides_cached_selection(async_client, native_pool):
    _, seen, _ = native_pool
    payload = {"model": MODELS[0], "input": "hello", "stream": True}
    first = await async_client.post("/v1/responses", json=payload)
    assert "response.completed" in first.text
    assert len(seen) == 1 and seen[0] in {"free-a", "free-b"}
    async with SessionLocal() as session:
        await session.execute(update(Account).where(Account.plan_type == "free").values(plan_type="plus"))
        await session.commit()
    # Deliberately leave the 60-second selection snapshot intact. Dispatch must
    # use current persisted plan evidence, not that stale eligibility snapshot.
    seen.clear()
    second = await async_client.post("/v1/responses", json=payload)
    assert "error" in second.text and "response.completed" not in second.text
    assert not seen


@pytest.mark.parametrize("transport", ["stream", "compact"])
async def test_model_plan_retry_stays_in_free_pool(async_client, native_pool, monkeypatch, transport):
    _, seen, _ = native_pool
    failed_account = None

    def attempt(account_id):
        nonlocal failed_account
        seen.append(account_id)
        failed_account = failed_account or account_id
        if account_id == failed_account:
            raise ProxyResponseError(
                500, openai_error("server_error", "retry"), failure_phase="status", retryable_same_contract=True
            )

    async def stream(payload, headers, access_token, account_id, **kwargs):
        attempt(account_id)
        yield _success_sse_event()

    async def compact(payload, headers, access_token, account_id):
        attempt(account_id)
        return CompactResponsePayload.model_validate({"object": "response.compaction", "output": []})

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(proxy_module, "core_compact_responses", compact)
    path = "/backend-api/codex/responses" + ("/compact" if transport == "compact" else "")
    payload = {"model": MODELS[0], "instructions": "hi", "input": "hello"}
    if transport == "stream":
        payload["stream"] = True
    response = await async_client.post(path, json=payload)
    assert response.status_code == 200, response.text
    assert seen.count(failed_account) == 3
    assert set(seen) == {"free-a", "free-b"}
    if transport == "stream":
        assert "response.completed" in response.text


@pytest.mark.parametrize("failure", ["invalid-json", "invalid-plan", "unavailable"])
async def test_model_plan_persisted_evidence_fails_closed_sanitized(async_client, native_pool, monkeypatch, failure):
    _, seen, service = native_pool
    record_errors = AsyncMock(wraps=service._load_balancer.record_errors)
    monkeypatch.setattr(service._load_balancer, "record_errors", record_errors)
    if failure == "unavailable":

        async def broken():
            raise RuntimeError("private database credential")

        monkeypatch.setattr(model_admission, "get_settings_cache", lambda: SimpleNamespace(get=broken))
    else:
        raw = "private invalid json" if failure == "invalid-json" else json.dumps({MODELS[0]: ["secret-unknown-plan"]})
        async with SessionLocal() as session:
            await session.execute(update(DashboardSettings).values(model_plan_routing_policies_json=raw))
            await session.commit()
        await get_settings_cache().invalidate()
    response = await async_client.post("/v1/responses", json={"model": MODELS[0], "input": "hello", "stream": False})
    # Nonstream Responses maps the existing upstream_unavailable envelope to 502.
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "upstream_unavailable"
    assert "private" not in response.text and "secret" not in response.text
    assert not seen
    record_errors.assert_not_awaited()


async def test_model_plan_does_not_grant_missing_catalog_entitlement(async_client, native_pool, monkeypatch):
    import app.modules.proxy.load_balancer as balancer_module
    from app.core.openai.model_registry import ModelRegistry

    _, seen, _ = native_pool
    registry = ModelRegistry(ttl_seconds=60)
    model = registry.get_models_with_fallback()[MODELS[0]]
    await registry.update({"plus": [model]})
    assert registry.plan_types_for_model(MODELS[0]) == {"plus"}
    monkeypatch.setattr(balancer_module, "get_model_registry", lambda: registry)
    response = await async_client.post("/v1/responses", json={"model": MODELS[0], "input": "hello", "stream": True})
    assert "error" in response.text
    assert not seen


async def test_model_plan_cannot_manufacture_unique_conversation_owner(native_pool):
    accounts, _, service = native_pool
    # Two plausible owners remain ambiguous even though only Free survives
    # routing eligibility. This uses the same real owner-selection path as continuations.
    selection = await service._load_balancer.select_account(
        model=MODELS[0], account_ids=[accounts["paid"], accounts["free-a"]], require_unambiguous_account=True
    )
    assert selection.account is None
    assert selection.error_code == "conversation_owner_unavailable"
    pinned = await service._load_balancer.select_account(
        model=MODELS[0],
        required_account_id=accounts["paid"],
        required_account_is_ownership_constraint=True,
        required_continuity_owner=True,
    )
    assert pinned.account is None


UNCONFIGURED_MODEL = "gpt-5.4"
_TIER_KEYS = ("service_tiers", "additional_speed_tiers", "default_service_tier")


@pytest.fixture
async def tier_pool(native_pool, monkeypatch):
    """Authoritative catalog where only the paid account offers ``priority``."""
    from dataclasses import replace

    from app.core.openai.model_registry import get_model_registry

    accounts, seen, service = native_pool
    registry = get_model_registry()
    fallback = registry.get_models_with_fallback()

    def catalog_model(slug, *, tiers):
        raw = {key: value for key, value in fallback[slug].raw.items() if key not in _TIER_KEYS}
        if tiers:
            raw["service_tiers"] = [{"id": "priority", "name": "Fast"}]
        return replace(fallback[slug], raw=raw)

    plus_models = [catalog_model(slug, tiers=True) for slug in (MODELS[0], UNCONFIGURED_MODEL)]
    free_models = [catalog_model(slug, tiers=False) for slug in (MODELS[0], UNCONFIGURED_MODEL)]
    plans = {accounts["paid"]: "plus", accounts["free-a"]: "free", accounts["free-b"]: "free"}
    await registry.update(
        {"plus": plus_models, "free": free_models},
        per_account_results={
            account_id: (plan, plus_models if plan == "plus" else free_models) for account_id, plan in plans.items()
        },
        active_account_plans=plans,
    )
    snapshot = registry.get_snapshot()
    assert snapshot is not None and snapshot.account_catalogs_authoritative
    payloads = []

    async def stream(payload, headers, access_token, account_id, **kwargs):
        seen.append(account_id)
        payloads.append(payload.to_payload())
        yield _success_sse_event()

    async def compact(payload, headers, access_token, account_id):
        seen.append(account_id)
        payloads.append(payload.to_payload())
        return CompactResponsePayload.model_validate({"object": "response.compaction", "output": []})

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(proxy_module, "core_compact_responses", compact)
    return accounts, seen, payloads


@pytest.mark.parametrize("service_tier", ["priority", "fast"])
@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
async def test_plan_restricted_model_drops_a_tier_no_allowed_plan_offers(
    async_client, tier_pool, path, stream, service_tier
):
    _, seen, payloads = tier_pool
    response = await async_client.post(
        path, json={"model": MODELS[0], "input": "hello", "stream": stream, "service_tier": service_tier}
    )
    assert response.status_code == 200, response.text
    assert seen and seen[-1] in {"free-a", "free-b"}, response.text
    assert "service_tier" not in payloads[-1]


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/backend-api/codex/responses/compact"])
async def test_plan_restricted_tier_fallback_covers_chat_and_compact(async_client, tier_pool, path):
    _, seen, payloads = tier_pool
    payload = {"model": MODELS[0], "instructions": "hi", "input": "hello", "service_tier": "priority"}
    if path.endswith("completions"):
        payload = {
            "model": MODELS[0],
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
            "service_tier": "priority",
        }
    response = await async_client.post(path, json=payload)
    assert response.status_code == 200, response.text
    assert seen and seen[-1] in {"free-a", "free-b"}, response.text
    assert "service_tier" not in payloads[-1]


async def test_unconfigured_model_keeps_an_explicit_tier(async_client, tier_pool):
    _, seen, payloads = tier_pool
    response = await async_client.post(
        "/v1/responses",
        json={"model": UNCONFIGURED_MODEL, "input": "hello", "stream": True, "service_tier": "priority"},
    )
    assert response.status_code == 200, response.text
    assert seen == ["paid"]
    assert payloads[-1]["service_tier"] == "priority"


async def test_plan_restricted_model_keeps_a_tier_an_allowed_plan_offers(async_client, tier_pool):
    _, seen, payloads = tier_pool
    saved = await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": {MODELS[0]: ["free", "plus"]}})
    assert saved.status_code == 200, saved.text
    get_account_selection_cache().invalidate()
    response = await async_client.post(
        "/v1/responses", json={"model": MODELS[0], "input": "hello", "stream": True, "service_tier": "priority"}
    )
    assert response.status_code == 200, response.text
    assert seen == ["paid"]
    assert payloads[-1]["service_tier"] == "priority"
