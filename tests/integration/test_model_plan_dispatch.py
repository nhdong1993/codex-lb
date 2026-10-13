from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, update

import app.modules.proxy.service as proxy_module
from app.core.clients.proxy import ProxyResponseError
from app.core.errors import openai_error
from app.core.openai.models import CompactResponsePayload
from app.db.models import Account, ApiKeyUsageReservation
from app.db.session import SessionLocal
from app.modules.proxy import model_admission
from app.modules.proxy.work_admission import WorkAdmissionController
from app.modules.usage import plan_checks
from tests.integration import test_model_plan_routing as routing_fixtures
from tests.integration.test_model_plan_routing import MODELS
from tests.integration.test_proxy_transient_retry import _success_sse_event

native_pool = routing_fixtures.native_pool
pytestmark = pytest.mark.integration


@pytest.fixture
async def dispatch_pool(async_client, native_pool, monkeypatch):
    accounts, seen, service = native_pool
    saved = await async_client.put("/api/settings", json={"apiKeyAuthEnabled": True})
    assert saved.status_code == 200
    created = await async_client.post(
        "/api/api-keys/",
        json={
            "name": "final-dispatch",
            "limits": [{"limitType": "total_tokens", "limitWindow": "weekly", "maxValue": 1_000_000}],
        },
    )
    assert created.status_code == 200, created.text
    admission = WorkAdmissionController(
        token_refresh_limit=0, websocket_connect_limit=0, response_create_limit=1, compact_response_create_limit=1
    )
    monkeypatch.setattr(service, "_get_work_admission", lambda: admission)
    health = []
    for owner, name in (
        (service, "_handle_stream_error"),
        (service, "_handle_proxy_error"),
        (service._load_balancer, "record_errors"),
        (service._load_balancer, "record_success"),
        (service._load_balancer, "mark_permanent_failure"),
    ):
        spy = AsyncMock(wraps=getattr(owner, name))
        monkeypatch.setattr(owner, name, spy)
        health.append(spy)
    return accounts, seen, service, admission, created.json(), health


async def _change_eligibility(async_client, change):
    if change == "policy":
        saved = await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": {MODELS[0]: ["plus"]}})
        assert saved.status_code == 200, saved.text
    else:
        async with SessionLocal() as session:
            await session.execute(update(Account).where(Account.plan_type == "free").values(plan_type="plus"))
            await session.commit()


async def _request(async_client, key, transport, *, model=MODELS[0], file_id=None, previous_response_id=None):
    payload = {"model": model, "instructions": "hi", "input": "hello"}
    if file_id:
        payload["input"] = [{"role": "user", "content": [{"type": "input_file", "file_id": file_id}]}]
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    if transport == "stream":
        payload["stream"] = True
    path = "/backend-api/codex/responses" + ("/compact" if transport == "compact" else "")
    return await async_client.post(path, json=payload, headers={"Authorization": f"Bearer {key['key']}"})


async def _assert_denied_and_clean(response, pool, *, health_neutral=True):
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "upstream_unavailable"
    await _assert_clean(pool, health_neutral=health_neutral)


async def _assert_clean(pool, *, health_neutral=True):
    accounts, _, service, admission, key, health = pool
    assert await service.drain_persistence_tasks(timeout_seconds=5)
    async with SessionLocal() as session:
        statuses = list(
            await session.scalars(
                select(ApiKeyUsageReservation.status).where(ApiKeyUsageReservation.api_key_id == key["id"])
            )
        )
    assert len(statuses) == 1 and statuses[0] in {"released", "settled", "finalized"}
    for account_id in accounts.values():
        assert await service._load_balancer.account_pressure_snapshot(account_id) == (0, 0, 0.0)
    assert admission._response_create.semaphore._value == 1
    assert admission._compact_response_create.semaphore._value == 1
    if health_neutral:
        for spy in health:
            spy.assert_not_awaited()


@pytest.mark.parametrize("transport", ["stream", "compact"])
@pytest.mark.parametrize("change", ["policy", "plan"])
@pytest.mark.parametrize("seam", ["admission", "route"])
async def test_native_final_dispatch_rechecks_eligibility(
    async_client, dispatch_pool, monkeypatch, transport, change, seam
):
    _, seen, service, admission, key, _ = dispatch_pool
    # Compact already owns a selection lease: the global create gate and route
    # resolution are real final seams on both public HTTP paths.
    target, name = (
        (admission, "acquire_response_create")
        if seam == "admission"
        else (service, "_resolve_upstream_route_for_account")
    )
    original = getattr(target, name)
    reached = False

    async def change_after_wait(*args, **kwargs):
        nonlocal reached
        result = await original(*args, **kwargs)
        if not reached:
            reached = True
            await _change_eligibility(async_client, change)
        return result

    monkeypatch.setattr(target, name, change_after_wait)
    response = await _request(async_client, key, transport)
    assert reached, "actual final admission seam must be exercised"
    assert not seen, f"forbidden dispatch after {change} became effective: {seen}"
    await _assert_denied_and_clean(response, dispatch_pool)


@pytest.mark.parametrize("transport", ["stream", "compact"])
@pytest.mark.parametrize("change", ["policy", "plan"])
@pytest.mark.parametrize("status", [500, 401, 502])
async def test_native_same_account_retry_rechecks_eligibility(
    async_client, dispatch_pool, monkeypatch, transport, change, status
):
    accounts, seen, service, _, key, health = dispatch_pool
    refreshes = []

    async def fresh(account, *, force=False, **kwargs):
        refreshes.append(force)
        return account

    monkeypatch.setattr(service, "_ensure_fresh_with_budget", fresh)

    async def attempt(account_id):
        seen.append(account_id)
        if len(seen) == 1:
            await _change_eligibility(async_client, change)
            raise ProxyResponseError(
                status,
                openai_error("invalid_api_key" if status == 401 else "server_error", "retry"),
                failure_phase="connect" if status == 502 else "status",
                retryable_same_contract=True,
            )

    async def stream(payload, headers, access_token, account_id, **kwargs):
        await attempt(account_id)
        yield _success_sse_event()

    async def compact(payload, headers, access_token, account_id):
        await attempt(account_id)
        return CompactResponsePayload.model_validate({"object": "response.compaction", "output": []})

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(proxy_module, "core_compact_responses", compact)
    response = await _request(async_client, key, transport)
    first = seen[0]
    assert first.startswith("free-"), seen
    # After the change only these accounts may receive the request: the policy
    # change admits only the plus account; the plan change leaves none.
    eligible = ["paid"] if change == "policy" else []
    handle_stream_error, handle_proxy_error, record_errors, record_success, mark_permanent_failure = health
    if transport == "stream" and status == 502:
        # A confirmed pre-dispatch connect failure moves a movable stream
        # instead of retrying this account; the move stays inside the effective
        # pool, and an empty pool surfaces the existing exhausted-retry error.
        assert seen[1:] == eligible, f"forbidden retry: {seen}"
        assert response.status_code == (200 if eligible else 502), response.text
        await _assert_clean(dispatch_pool, health_neutral=False)
        # Only the existing route backoff for the failed connect is recorded.
        record_errors.assert_awaited_once()
        assert record_errors.await_args.args[0].id == accounts[first]
        for spy in (handle_stream_error, handle_proxy_error, mark_permanent_failure):
            spy.assert_not_awaited()
        assert record_success.await_count == len(eligible)
    else:
        assert seen == [first], f"forbidden retry: {seen}"
        if transport == "stream" and status == 401:
            # The allowed first dispatch's upstream 401 keeps its existing
            # immediate penalty; the admission denial itself adds none.
            await _assert_denied_and_clean(response, dispatch_pool, health_neutral=False)
            handle_stream_error.assert_awaited_once()
            assert handle_stream_error.await_args.args[0].id == accounts[first]
            assert handle_stream_error.await_args.kwargs == {"http_status": 401}
            record_errors.assert_awaited_once()
            for spy in (handle_proxy_error, record_success, mark_permanent_failure):
                spy.assert_not_awaited()
        else:
            await _assert_denied_and_clean(response, dispatch_pool)

    assert any(refreshes) is (status == 401)


@pytest.mark.parametrize("transport", ["stream", "compact"])
@pytest.mark.parametrize("owner", ["file", "conversation"])
async def test_native_final_denial_never_moves_pinned_owner(async_client, dispatch_pool, monkeypatch, transport, owner):
    accounts, seen, service, admission, key, _ = dispatch_pool
    if owner == "file":
        await service._pin_file_account("file-dispatch-owner", accounts["free-a"])
    else:
        monkeypatch.setattr(
            service, "_resolve_websocket_previous_response_owner", AsyncMock(return_value=accounts["free-a"])
        )
    acquire = admission.acquire_response_create

    async def deny_after_wait(*args, **kwargs):
        result = await acquire(*args, **kwargs)
        await _change_eligibility(async_client, "policy")
        return result

    monkeypatch.setattr(admission, "acquire_response_create", deny_after_wait)
    response = await _request(
        async_client,
        key,
        transport,
        file_id="file-dispatch-owner" if owner == "file" else None,
        previous_response_id="resp_dispatch_owner" if owner == "conversation" else None,
    )
    assert not seen, f"pinned work was sent or moved to a different owner: {seen}"
    await _assert_denied_and_clean(response, dispatch_pool)


@pytest.mark.parametrize("transport", ["stream", "compact"])
async def test_native_final_lookup_failure_is_sanitized_and_health_neutral(
    async_client, dispatch_pool, monkeypatch, transport
):
    _, seen, _, admission, key, _ = dispatch_pool
    acquire = admission.acquire_response_create

    def unavailable_session():
        raise RuntimeError("secret database connection details")

    async def fail_after_wait(*args, **kwargs):
        result = await acquire(*args, **kwargs)
        monkeypatch.setattr(model_admission, "get_background_session", unavailable_session)
        return result

    monkeypatch.setattr(admission, "acquire_response_create", fail_after_wait)
    response = await _request(async_client, key, transport)
    assert not seen
    assert "secret" not in response.text
    await _assert_denied_and_clean(response, dispatch_pool)


@pytest.mark.parametrize("transport", ["stream", "compact"])
async def test_native_final_lookup_cancellation_releases_admission_and_reservation(
    async_client, dispatch_pool, monkeypatch, transport
):
    _, seen, _, _, key, _ = dispatch_pool
    reached = asyncio.Event()

    async def wait_at_final_lookup(*args):
        reached.set()
        await asyncio.Future()

    monkeypatch.setattr(model_admission, "ensure_native_dispatch_allowed", wait_at_final_lookup)
    task = asyncio.create_task(_request(async_client, key, transport))
    try:
        await asyncio.wait_for(reached.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert not seen
    await _assert_clean(dispatch_pool)


@pytest.mark.parametrize("transport", ["stream", "compact"])
async def test_unconfigured_model_same_account_retry_is_preserved(async_client, dispatch_pool, monkeypatch, transport):
    _, seen, _, _, key, _ = dispatch_pool

    async def attempt(account_id):
        seen.append(account_id)
        if len(seen) == 1:
            await _change_eligibility(async_client, "policy")
            raise ProxyResponseError(500, openai_error("server_error", "retry"))

    async def stream(payload, headers, access_token, account_id, **kwargs):
        await attempt(account_id)
        yield _success_sse_event()

    async def compact(payload, headers, access_token, account_id):
        await attempt(account_id)
        return CompactResponsePayload.model_validate({"object": "response.compaction", "output": []})

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(proxy_module, "core_compact_responses", compact)
    response = await _request(async_client, key, transport, model="gpt-5.4")
    assert response.status_code == 200, response.text
    assert len(seen) == 2 and seen[0] == seen[1]
    await _assert_clean(dispatch_pool, health_neutral=False)


@pytest.mark.parametrize("transport", ["stream", "compact"])
async def test_unconfigured_model_dispatch_ignores_concurrent_plan_check_rejection(
    async_client, dispatch_pool, monkeypatch, transport
):
    accounts, seen, _, admission, key, _ = dispatch_pool
    acquire = admission.acquire_response_create
    rejected: set[str] = set()

    async def reject_after_selection(*args, **kwargs):
        result = await acquire(*args, **kwargs)
        # A concurrent request's plan check rejects this unconfigured model on
        # every account after selection; final dispatch keeps existing behavior.
        async with SessionLocal() as session:
            accounts = list(await session.scalars(select(Account)))
        for account in accounts:
            await plan_checks.request_plan_check(account, model="gpt-5.4")
        rejected.update(await plan_checks.rejected_model_account_ids(accounts, "gpt-5.4"))
        return result

    monkeypatch.setattr(admission, "acquire_response_create", reject_after_selection)
    response = await _request(async_client, key, transport, model="gpt-5.4")
    assert response.status_code == 200, response.text
    assert rejected == set(accounts.values())
    assert len(seen) == 1, seen
    await _assert_clean(dispatch_pool, health_neutral=False)
