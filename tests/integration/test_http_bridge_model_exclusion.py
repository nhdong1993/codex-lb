from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from asyncpg import InvalidPasswordError
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import create_async_engine

import app.modules.proxy.service as proxy_module
from app.core.utils.time import utcnow
from app.db.models import (
    Account,
    AccountPlanCheck,
    AccountStatus,
    ApiKeyUsageReservation,
    StickySession,
    StickySessionKind,
)
from app.db.session import SessionLocal
from app.dependencies import get_proxy_service_for_app
from app.modules.proxy.load_balancer import AccountSelection
from app.modules.proxy.sticky_repository import StickySessionsRepository
from app.modules.usage import plan_checks
from tests.integration.test_http_responses_bridge import (
    _cleanup_http_bridge_sessions as _cleanup_http_bridge_sessions,
)
from tests.integration.test_http_responses_bridge import (
    _collect_sse_events,
    _FakeBridgeUpstreamWebSocket,
    _get_account,
    _import_account,
    _install_bridge_settings,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def bridge(async_client, app_instance, monkeypatch):
    _install_bridge_settings(monkeypatch, enabled=True)
    accounts = [
        await _get_account(await _import_account(async_client, name, f"{name}@example.com"))
        for name in ("model-a", "model-b")
    ]
    upstreams = {account.chatgpt_account_id: _FakeBridgeUpstreamWebSocket(account.id) for account in accounts}
    selections = []
    health_writes = []
    real_select = proxy_module.ProxyService._select_account_with_budget

    async def select(self, *args, **kwargs):
        excluded = await plan_checks.rejected_model_account_ids(accounts, kwargs["model"])
        excluded |= set(kwargs.get("exclude_account_ids") or ())
        preferred = kwargs.get("preferred_account_id")
        account = next((a for a in accounts if a.id not in excluded and (preferred is None or a.id == preferred)), None)
        selections.append(account.id if account else None)
        return AccountSelection(
            account=account,
            error_message=None if account else "Owner unavailable",
            error_code=None if account else "previous_response_owner_unavailable",
        )

    async def fresh(self, target, **kwargs):
        return target

    async def connect(headers, access_token, account_id_header, **kwargs):
        return upstreams[account_id_header]

    async def health(self, *args, **kwargs):
        health_writes.append((args, kwargs))
        raise AssertionError("Local model exclusion must not penalize account health")

    monkeypatch.setattr(proxy_module.ProxyService, "_select_account_with_budget", select)
    monkeypatch.setattr(proxy_module.ProxyService, "_ensure_fresh_with_budget", fresh)
    monkeypatch.setattr(proxy_module, "connect_responses_websocket", connect)
    monkeypatch.setattr(proxy_module.ProxyService, "_handle_stream_error", health)
    return SimpleNamespace(
        accounts=accounts,
        first=upstreams[accounts[0].chatgpt_account_id],
        second=upstreams[accounts[1].chatgpt_account_id],
        selections=selections,
        health_writes=health_writes,
        service=get_proxy_service_for_app(app_instance),
        real_select=real_select,
    )


def body(text="hello"):
    return {"model": "gpt-5.1", "input": text, "prompt_cache_key": "model-exclusion-thread"}


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize("owner", ["movable", "conversation", "file"])
async def test_bridge_reuse_honors_model_exclusion(async_client, bridge, path, owner):
    # The public JSON route establishes the same upstream bridge used by the
    # backend SSE continuation route below.
    first = await async_client.post("/v1/responses", json=body())
    assert first.status_code == 200, first.text
    await plan_checks.request_plan_check(bridge.accounts[0], model="gpt-5.1")
    payload = body("next")
    if owner == "conversation":
        payload["previous_response_id"] = first.json()["id"]
    elif owner == "file":
        await bridge.service._pin_file_account("file-model-owner", bridge.accounts[0].id)
        payload["input"] = [{"type": "input_file", "file_id": "file-model-owner"}]
    second = await async_client.post(path, json=payload)
    assert len(bridge.first.sent_text) == 1
    if owner == "movable":
        assert second.status_code == 200, second.text
        assert len(bridge.second.sent_text) == 1
    else:
        assert "previous_response_owner_unavailable" in second.text, second.text
        assert not bridge.second.sent_text
    assert not bridge.health_writes


@pytest.mark.parametrize("expired", [False, True])
async def test_bridge_unrelated_or_expired_rejection_keeps_reuse(async_client, bridge, expired):
    first = await async_client.post("/v1/responses", json=body())
    assert first.status_code == 200
    await plan_checks.request_plan_check(bridge.accounts[0], model="gpt-5.1" if expired else "other-model")
    if expired:
        async with SessionLocal() as session:
            await session.execute(update(AccountPlanCheck).values(requested_at=utcnow() - timedelta(minutes=3)))
            await session.commit()
    second = await async_client.post("/v1/responses", json={**body("next"), "previous_response_id": first.json()["id"]})
    assert second.status_code == 200, second.text
    assert len(bridge.first.sent_text) == 2 and not bridge.second.sent_text
    assert len(bridge.selections) == 1


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize(
    "failure",
    ["exclusion", "cancel", "database", "pool_timeout", "connection_refused", "connect_timeout", "driver_auth"],
)
async def test_bridge_late_exclusion_settles_reservation_and_preserves_sibling(
    async_client, bridge, monkeypatch, failure, path
):
    assert (await async_client.put("/api/settings", json={"apiKeyAuthEnabled": True})).status_code == 200
    (await proxy_module.get_settings_cache().get()).api_key_auth_enabled = True
    key_response = await async_client.post(
        "/api/api-keys/", json={"name": "model-admission", "weeklyTokenLimit": 1000000}
    )
    assert key_response.status_code == 200
    headers = {"Authorization": f"Bearer {key_response.json()['key']}"}
    real_send = bridge.first.send_text
    first_sent = asyncio.Event()
    held_terminal = []
    states = []
    real_admission = proxy_module.ProxyService._acquire_request_state_response_create_admission
    real_query = plan_checks.rejected_model_account_ids
    lookup_started = asyncio.Event()
    lookup_release = asyncio.Event()

    async def query(accounts, model):
        if len(states) == 2:
            if failure == "cancel":
                lookup_started.set()
                await lookup_release.wait()
            elif failure == "database":
                raise OperationalError("select account_plan_checks", {}, Exception("private driver details"))
            elif failure == "pool_timeout":
                raise SQLAlchemyTimeoutError("private pool details")
            elif failure in {"connection_refused", "connect_timeout", "driver_auth"}:
                await fail_driver_connect(failure)
        return await real_query(accounts, model)

    async def send(text):
        await real_send(text)
        created = bridge.first._messages.get_nowait()
        held_terminal.append(bridge.first._messages.get_nowait())
        bridge.first._messages.put_nowait(created)
        first_sent.set()

    async def admission(self, state, **kwargs):
        await real_admission(self, state, **kwargs)
        states.append(state)
        if len(states) == 2 and failure == "exclusion":
            await plan_checks.request_plan_check(bridge.accounts[0], model=state.model)

    monkeypatch.setattr(bridge.first, "send_text", send)
    monkeypatch.setattr(proxy_module.ProxyService, "_acquire_request_state_response_create_admission", admission)
    monkeypatch.setattr(plan_checks, "rejected_model_account_ids", query)
    first = asyncio.create_task(async_client.post("/v1/responses", json=body(), headers=headers))
    second = None
    try:
        await asyncio.wait_for(first_sent.wait(), 5)
        async with asyncio.timeout(5):
            while not states[0].response_id:
                await asyncio.sleep(0.001)
        second = asyncio.create_task(
            async_client.post(
                path, json={**body("next"), "previous_response_id": states[0].response_id}, headers=headers
            )
        )
        if failure == "cancel":
            await asyncio.wait_for(lookup_started.wait(), 5)
            second.cancel()
            with pytest.raises(asyncio.CancelledError):
                await second
        else:
            result = await asyncio.wait_for(second, 5)
            if failure == "exclusion":
                assert "previous_response_owner_unavailable" in result.text, result.text
            else:
                assert result.status_code == 503, result.text
                assert result.json()["error"]["code"] == "upstream_unavailable"
                assert result.json()["error"]["message"] == (
                    "Account model availability could not be checked; retry later."
                )
        assert len(bridge.first.sent_text) == 1 and not bridge.second.sent_text
        assert not bridge.first.closed and not first.done()
        rejected = states[1]
        assert rejected.response_create_sent_at is None
        assert not rejected.response_create_gate_acquired
        assert rejected.response_create_admission is None
        assert rejected.account_response_create_lease is None
        async with SessionLocal() as session:
            reservations = list(await session.scalars(select(ApiKeyUsageReservation)))
        # The accepted sibling still owns its reservation; only the unsent
        # request may have been released at this point.
        assert sorted(row.status for row in reservations) == ["released", "reserved"]
        bridge.first._messages.put_nowait(held_terminal.pop())
        assert (await asyncio.wait_for(first, 5)).status_code == 200
        async with SessionLocal() as session:
            reservations = list(await session.scalars(select(ApiKeyUsageReservation)))
        assert len(reservations) == 2
        assert sorted(row.status for row in reservations) == ["finalized", "released"]
        assert not bridge.health_writes
    finally:
        lookup_release.set()
        for terminal in held_terminal:
            bridge.first._messages.put_nowait(terminal)
        if not first.done():
            first.cancel()
        if second is not None and not second.done():
            second.cancel()
        await asyncio.gather(*(task for task in (first, second) if task is not None), return_exceptions=True)


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize("inflight", [False, True])
async def test_excluded_cached_peer_does_not_block_healthy_file_owner(
    async_client, bridge, monkeypatch, path, inflight
):
    real_send = bridge.first.send_text
    first_sent = asyncio.Event()
    held_terminal = []

    async def send(text):
        await real_send(text)
        created = bridge.first._messages.get_nowait()
        held_terminal.append(bridge.first._messages.get_nowait())
        bridge.first._messages.put_nowait(created)
        first_sent.set()

    monkeypatch.setattr(bridge.first, "send_text", send)
    first = asyncio.create_task(async_client.post("/v1/responses", json=body()))
    try:
        await asyncio.wait_for(first_sent.wait(), 5)
        session = next(iter(bridge.service._http_bridge_sessions.values()))
        async with asyncio.timeout(5):
            while not any(state.response_id for state in session.pending_requests):
                await asyncio.sleep(0.001)
        await plan_checks.request_plan_check(bridge.accounts[0], model="gpt-5.1")
        await bridge.service._pin_file_account("file-model-b", bridge.accounts[1].id)
        waits = []
        if inflight:
            bridge.service._http_bridge_sessions.pop(session.key)
            future = asyncio.get_running_loop().create_future()
            bridge.service._http_bridge_inflight_sessions[session.key] = future
            real_wait = proxy_module.ProxyService._await_http_bridge_registry_wait

            async def finish_creation(self, pending, *, timeout):
                assert pending is future
                waits.append(pending)
                self._http_bridge_sessions[session.key] = session
                self._http_bridge_inflight_sessions.pop(session.key)
                future.set_result(session)
                return await real_wait(self, pending, timeout=timeout)

            monkeypatch.setattr(proxy_module.ProxyService, "_await_http_bridge_registry_wait", finish_creation)
        response = await asyncio.wait_for(
            async_client.post(
                path, json={**body("file request"), "input": [{"type": "input_file", "file_id": "file-model-b"}]}
            ),
            5,
        )
        assert response.status_code == 200, response.text
        assert bridge.selections == [account.id for account in bridge.accounts]
        assert len(bridge.first.sent_text) == 1 and len(bridge.second.sent_text) == 1
        assert len(waits) == int(inflight)
        assert not bridge.first.closed and not first.done()
        bridge.first._messages.put_nowait(held_terminal.pop())
        assert (await asyncio.wait_for(first, 5)).status_code == 200
        async with asyncio.timeout(5):
            while not bridge.first.closed or id(session) in bridge.service._http_bridge_detached_sessions:
                await asyncio.sleep(0.001)
        assert not bridge.health_writes
    finally:
        for terminal in held_terminal:
            bridge.first._messages.put_nowait(terminal)
        if not first.done():
            first.cancel()
        await asyncio.gather(first, return_exceptions=True)


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize("failure", ["database", "connection_refused", "connect_timeout", "driver_auth"])
async def test_bridge_cache_evidence_failure_is_sanitized(async_client, bridge, monkeypatch, path, failure):
    first = await async_client.post("/v1/responses", json=body())
    assert first.status_code == 200

    async def failed_query(accounts, model):
        assert [account.id for account in accounts] == [bridge.accounts[0].id]
        if failure == "database":
            raise OperationalError("select account_plan_checks", {}, Exception("private driver details"))
        await fail_driver_connect(failure)

    monkeypatch.setattr(plan_checks, "rejected_model_account_ids", failed_query)
    response = await async_client.post(path, json=body())
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "upstream_unavailable"
    assert response.json()["error"]["message"] == "Account model availability could not be checked; retry later."
    assert len(bridge.first.sent_text) == 1 and not bridge.second.sent_text
    assert not bridge.first.closed
    assert not bridge.health_writes


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize("failure", ["database", "connection_refused", "connect_timeout", "driver_auth"])
async def test_bridge_initial_selection_evidence_failure_is_sanitized(async_client, bridge, monkeypatch, path, failure):
    monkeypatch.setattr(proxy_module.ProxyService, "_select_account_with_budget", bridge.real_select)

    async def failed_query(accounts, model):
        if not accounts:
            return set()
        if failure == "database":
            raise OperationalError("select account_plan_checks", {}, Exception("private driver details"))
        await fail_driver_connect(failure)

    monkeypatch.setattr(plan_checks, "rejected_model_account_ids", failed_query)
    response = await async_client.post(path, json=body())
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "upstream_unavailable"
    assert response.json()["error"]["message"] == "Account model availability could not be checked; retry later."
    assert not bridge.first.sent_text and not bridge.second.sent_text
    assert not bridge.health_writes


async def fail_driver_connect(failure):
    async def connect():
        # Exercise SQLAlchemy's asyncpg connection boundary without relying
        # on a live server or an assumed-unused host port.
        if failure == "connection_refused":
            raise ConnectionRefusedError("private database host:5432")
        if failure == "connect_timeout":
            raise TimeoutError("private database connection timeout")
        if failure == "driver_auth":
            raise InvalidPasswordError("private database authentication details")
        raise AssertionError(f"Unexpected failure mode: {failure}")

    engine = create_async_engine("postgresql+asyncpg://", async_creator=connect)
    try:
        async with engine.connect():
            pytest.fail("The failing connector must not return a connection")
    finally:
        await engine.dispose()


@pytest.mark.parametrize("dependency", ["active_owner", "previous_response", "file"])
async def test_model_exclusion_does_not_expand_goal_restart_authority(async_client, bridge, monkeypatch, dependency):
    # Use the actual sticky selector: model exclusion alone is never authority
    # to abandon a healthy legacy owner, nor a file/conversation dependency.
    monkeypatch.setattr(proxy_module.ProxyService, "_select_account_with_budget", bridge.real_select)
    owner = bridge.accounts[0]
    raw_session = "excluded-goal-owner"
    async with SessionLocal() as session:
        await StickySessionsRepository(session).upsert(raw_session, owner.id, kind=StickySessionKind.CODEX_SESSION)
    headers = {"session_id": raw_session}
    first = await _collect_sse_events(
        async_client,
        "/backend-api/codex/responses",
        headers=headers,
        json_body={"model": "gpt-5.1", "input": "first", "stream": True},
    )
    if dependency != "active_owner":
        async with SessionLocal() as session:
            await session.execute(
                update(Account).where(Account.id == owner.id).values(status=AccountStatus.QUOTA_EXCEEDED)
            )
            await session.commit()
    await plan_checks.request_plan_check(owner, model="gpt-5.1")
    payload = {
        "model": "gpt-5.1",
        "input": [
            {
                "role": "developer",
                "content": '<codex_internal_context source="goal">\nContinue working toward the active thread goal.',
            },
            {"role": "user", "content": "continue"},
        ],
        "stream": True,
    }
    if dependency == "previous_response":
        payload["previous_response_id"] = first[-1]["response"]["id"]
    elif dependency == "file":
        await bridge.service._pin_file_account("file-goal-owner", owner.id)
        payload["input"].append({"type": "input_file", "file_id": "file-goal-owner"})
    # Bound the existing no-account admission wait well below evidence expiry.
    monkeypatch.setattr(proxy_module.get_settings(), "http_responses_session_bridge_request_budget_seconds", 1.0)
    response = await async_client.post("/backend-api/codex/responses", headers=headers, json=payload)
    if dependency == "active_owner":
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == "hard_affinity_saturated"
    else:
        assert response.status_code == 502, response.text
        assert "previous_response_owner_unavailable" in response.text
    assert len(bridge.first.sent_text) == 1 and not bridge.second.sent_text
    async with SessionLocal() as session:
        row = await session.scalar(select(StickySession).where(StickySession.key == raw_session))
        assert row is not None and row.account_id == owner.id
        assert row.continuity_abandoned_at is None and row.continuity_abandonment_scope is None
    assert not bridge.health_writes
