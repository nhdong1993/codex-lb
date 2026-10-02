from __future__ import annotations

import asyncio
from concurrent.futures import CancelledError as FutureCancelledError
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError

import app.modules.proxy.api as proxy_api_module
import app.modules.proxy.service as proxy_module
from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountPlanCheck, AccountStatus
from app.db.session import SessionLocal
from app.modules.api_keys.service import ApiKeyUsageReservationData
from app.modules.proxy._service.websocket import mixin as websocket_mixin_module
from app.modules.proxy.account_cache import RoutingAvailabilityCache
from app.modules.usage import plan_checks
from tests.integration.test_http_bridge_model_exclusion import fail_driver_connect
from tests.integration.test_proxy_websocket_responses import (
    _FakeUpstreamMessage,
    _SequencedUpstreamWebSocket,
    _websocket_response_batch,
    _websocket_response_create,
    _websocket_settings,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def route(monkeypatch):
    availability = RoutingAvailabilityCache(SessionLocal)
    first = _SequencedUpstreamWebSocket([], deferred_message_batches=[_websocket_response_batch("resp_a")])
    second = _SequencedUpstreamWebSocket([], deferred_message_batches=[_websocket_response_batch("resp_b")])
    connected = []
    logs = []
    health_writes = []
    released = []
    states = []
    original_release = proxy_module.ProxyService._release_websocket_request_state_reservation
    original_admission = proxy_module.ProxyService._acquire_request_state_response_create_admission
    original_connect = proxy_module.ProxyService._connect_proxy_websocket

    async def seed():
        encrypted = TokenEncryptor().encrypt("test-only")
        async with SessionLocal() as session:
            session.add_all(
                Account(
                    id=account_id,
                    chatgpt_account_id=account_id,
                    email=f"{account_id}@example.com",
                    plan_type="plus",
                    access_token_encrypted=encrypted,
                    refresh_token_encrypted=encrypted,
                    id_token_encrypted=encrypted,
                    last_refresh=datetime.now(timezone.utc),
                    status=AccountStatus.ACTIVE,
                )
                for account_id in ("account_a", "account_b")
            )
            await session.commit()
        await availability.refresh_from_db()

    async def change_status(status):
        # Simulate a peer committing a status and this replica receiving the
        # existing account_routing invalidation callback. The socket keeps
        # its original detached ACTIVE Account instance.
        async with SessionLocal() as session:
            if status is None:
                await session.execute(delete(Account).where(Account.id == "account_a"))
            else:
                await session.execute(update(Account).where(Account.id == "account_a").values(status=status))
            await session.commit()
        await availability.refresh_from_db()

    async def allow_firewall(_websocket):
        return None

    async def allow_key(_authorization, **_kwargs):
        return None

    async def settings():
        return _websocket_settings()

    async def connect(self, _headers, *, request_state, websocket, client_send_lock, api_key, model, **_kwargs):
        async with SessionLocal() as session:
            query = select(Account).where(Account.status == AccountStatus.ACTIVE).order_by(Account.id)
            if request_state.preferred_account_id is not None:
                query = query.where(Account.id == request_state.preferred_account_id)
            candidates = list((await session.execute(query)).scalars())
        excluded = await plan_checks.rejected_model_account_ids(candidates, model)
        account = next((candidate for candidate in candidates if candidate.id not in excluded), None)
        if account is None:
            message = "Previous response owner account is unavailable; retry later."
            await self._emit_websocket_connect_failure(
                websocket,
                client_send_lock=client_send_lock,
                account_id=request_state.preferred_account_id,
                api_key=api_key,
                request_state=request_state,
                status_code=502,
                payload=proxy_module.openai_error("previous_response_owner_unavailable", message),
                error_code="previous_response_owner_unavailable",
                error_message=message,
            )
            return None, None
        connected.append(account.id)
        return account, first if account.id == "account_a" and not first.closed else second

    async def resolve_owner(self, **_kwargs):
        return "account_a"

    async def log(self, **kwargs):
        logs.append(kwargs)

    async def health(self, *args, **kwargs):
        health_writes.append((args, kwargs))
        raise AssertionError("Local account unavailability must not penalize upstream health")

    async def release(self, state):
        released.append(state)
        await original_release(self, state)

    async def admission(self, state, **kwargs):
        states.append(state)
        await original_admission(self, state, **kwargs)

    monkeypatch.setattr(websocket_mixin_module, "is_account_routing_unavailable", availability.is_unavailable)
    monkeypatch.setattr(proxy_api_module, "_websocket_firewall_denial_response", allow_firewall)
    monkeypatch.setattr(proxy_api_module, "validate_proxy_api_key_authorization", allow_key)
    monkeypatch.setattr(proxy_module, "get_settings_cache", lambda: SimpleNamespace(get=settings))
    monkeypatch.setattr(proxy_module.ProxyService, "_connect_proxy_websocket", connect)
    monkeypatch.setattr(proxy_module.ProxyService, "_resolve_websocket_previous_response_owner", resolve_owner)
    monkeypatch.setattr(proxy_module.ProxyService, "_write_request_log", log)
    monkeypatch.setattr(proxy_module.ProxyService, "_handle_stream_error", health)
    monkeypatch.setattr(proxy_module.ProxyService, "_release_websocket_request_state_reservation", release)
    monkeypatch.setattr(proxy_module.ProxyService, "_acquire_request_state_response_create_admission", admission)
    return SimpleNamespace(
        first=first,
        second=second,
        seed=seed,
        change_status=change_status,
        availability=availability,
        connected=connected,
        logs=logs,
        health_writes=health_writes,
        released=released,
        states=states,
        real_connect=original_connect,
    )


def complete_turn(websocket, text):
    websocket.send_json(_websocket_response_create(text))
    created = websocket.receive_json()
    completed = websocket.receive_json()
    assert created["type"] == "response.created"
    assert completed["type"] == "response.completed"
    return completed


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
def test_close_during_final_model_query_reconnects_unsent_turn(app_instance, route, monkeypatch, path):
    real_query = plan_checks.rejected_model_account_ids
    real_send = route.first.send_text
    real_close = route.first.close
    closed = asyncio.Event()
    attempted_after_close = []
    armed = False
    query_calls = 0

    async def close():
        await real_close()
        closed.set()

    async def query(accounts, model):
        nonlocal query_calls, armed
        result = await real_query(accounts, model)
        if armed:
            query_calls += 1
            if query_calls == 2:
                armed = False
                route.first._messages.put_nowait(_FakeUpstreamMessage("close", close_code=1000))
                await asyncio.wait_for(closed.wait(), 2)
        return result

    async def send(text):
        if route.first.closed:
            attempted_after_close.append(text)
            raise AssertionError("Unsent turn reached the retired socket")
        await real_send(text)

    monkeypatch.setattr(plan_checks, "rejected_model_account_ids", query)
    monkeypatch.setattr(route.first, "send_text", send)
    monkeypatch.setattr(route.first, "close", close)
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect(path) as websocket:
            complete_turn(websocket, "first")
            armed = True
            assert complete_turn(websocket, "second")["response"]["id"] == "resp_b"
    assert not attempted_after_close
    assert len(route.first.sent_text) == len(route.second.sent_text) == 1
    assert all(state.replay_count == 0 for state in route.states)
    assert all(state.account_response_create_lease is None for state in route.states)
    assert not route.health_writes


async def reject_model(model="gpt-5.4"):
    async with SessionLocal() as session:
        account = await session.get(Account, "account_a")
        assert account is not None
        await plan_checks.PlanCheckRepository(session).request(account, model=model)


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
def test_model_rejection_reselects_idle_reused_websocket(app_instance, route, path):
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect(path) as websocket:
            complete_turn(websocket, "first")
            client.portal.call(reject_model)
            assert complete_turn(websocket, "fresh")["response"]["id"] == "resp_b"
            assert route.first.closed
            assert len(route.first.sent_text) == len(route.second.sent_text) == 1
    assert route.connected == ["account_a", "account_b"]
    assert not route.health_writes


@pytest.mark.parametrize("owner_kind", ["conversation", "file"])
def test_model_rejection_preserves_hard_owner_on_reused_websocket(app_instance, route, owner_kind):
    from app.dependencies import get_proxy_service_for_app

    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect("/v1/responses") as websocket:
            complete_turn(websocket, "first")
            client.portal.call(reject_model)
            payload = _websocket_response_create("continue")
            if owner_kind == "conversation":
                payload["previous_response_id"] = "resp_a"
            else:
                service = get_proxy_service_for_app(app_instance)
                client.portal.call(service._pin_file_account, "file-model-excluded", "account_a")
                payload["input"] = [{"type": "input_file", "file_id": "file-model-excluded"}]
            websocket.send_json(payload)
            assert websocket.receive_json()["error"]["code"] == "previous_response_owner_unavailable"
            assert route.first.closed
            assert len(route.first.sent_text) == 1
            assert route.second.sent_text == []
    assert not route.health_writes


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize("failure", ["connection_refused", "driver_auth"])
def test_cold_websocket_evidence_failure_allows_same_socket_retry(app_instance, route, monkeypatch, path, failure):
    real_query = plan_checks.rejected_model_account_ids
    real_admission = proxy_module.ProxyService._acquire_request_state_response_create_admission
    broken = True
    connected = []
    released = []

    async def query(accounts, model):
        if broken and accounts:
            await fail_driver_connect(failure)
        return await real_query(accounts, model)

    async def admission(self, state, **kwargs):
        await real_admission(self, state, **kwargs)
        if broken:
            state.api_key_reservation = ApiKeyUsageReservationData("cold-reservation", "key", "gpt-5.4")

    async def release(self, reservation):
        if reservation is not None:
            released.append(reservation.reservation_id)

    async def fresh(self, account, **kwargs):
        return account

    async def connect(*args, **kwargs):
        connected.append(True)
        return route.first

    monkeypatch.setattr(plan_checks, "rejected_model_account_ids", query)
    monkeypatch.setattr(proxy_module.ProxyService, "_connect_proxy_websocket", route.real_connect)
    monkeypatch.setattr(proxy_module.ProxyService, "_ensure_fresh_with_budget", fresh)
    monkeypatch.setattr(proxy_module.ProxyService, "_acquire_request_state_response_create_admission", admission)
    monkeypatch.setattr(proxy_module.ProxyService, "_release_websocket_reservation", release)
    monkeypatch.setattr(proxy_module, "connect_responses_websocket", connect)
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect(path) as websocket:
            websocket.send_json(_websocket_response_create("cold lookup failure"))
            error = websocket.receive_json()
            assert error["type"] == "error"
            assert error["status"] == 503
            assert error["error"]["code"] == "upstream_unavailable"
            assert error["error"]["message"] == "Account model availability could not be checked; retry later."
            assert not connected and not route.first.sent_text
            assert released == ["cold-reservation"]
            state = route.states[-1]
            assert state.api_key_reservation is None and state.response_create_sent_at is None
            assert state.response_create_admission is None and state.account_response_create_lease is None
            assert not state.response_create_gate_acquired and state.websocket_stream_lease is None
            broken = False
            assert complete_turn(websocket, "retry")["response"]["id"] == "resp_a"
    assert len(connected) == len(route.first.sent_text) == 1
    assert not route.health_writes


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize("query_number", [1, 2])
@pytest.mark.parametrize("failure", ["database", "connection_refused", "connect_timeout", "driver_auth"])
def test_model_evidence_failure_preserves_accepted_sibling(
    app_instance, route, monkeypatch, path, query_number, failure
):
    route.first._deferred_message_batches.clear()
    route.first._deferred_message_batches.extend(
        [_websocket_response_batch("resp_a", completed=False), _websocket_response_batch("resp_retry")]
    )
    real_query = plan_checks.rejected_model_account_ids
    real_admission = proxy_module.ProxyService._acquire_request_state_response_create_admission
    armed = False
    calls = 0
    reservations_released = []

    async def query(accounts, model):
        nonlocal calls
        if armed:
            calls += 1
            if calls == query_number:
                if failure == "database":
                    raise OperationalError("select account_plan_checks", {}, Exception("private driver details"))
                await fail_driver_connect(failure)
        return await real_query(accounts, model)

    async def admission(self, state, **kwargs):
        await real_admission(self, state, **kwargs)
        if armed:
            state.api_key_reservation = ApiKeyUsageReservationData("unsent-reservation", "key", "gpt-5.4")

    async def release_reservation(self, reservation):
        if reservation is not None:
            reservations_released.append(reservation.reservation_id)

    monkeypatch.setattr(plan_checks, "rejected_model_account_ids", query)
    monkeypatch.setattr(proxy_module.ProxyService, "_acquire_request_state_response_create_admission", admission)
    monkeypatch.setattr(proxy_module.ProxyService, "_release_websocket_reservation", release_reservation)
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect(path) as websocket:
            websocket.send_json(_websocket_response_create("accepted"))
            assert websocket.receive_json()["type"] == "response.created"
            armed = True
            websocket.send_json(_websocket_response_create("unsent"))
            error = websocket.receive_json()
            assert error["type"] == "response.failed"
            assert error["response"]["error"]["code"] == "upstream_unavailable"
            assert (
                error["response"]["error"]["message"] == "Account model availability could not be checked; retry later."
            )
            state = route.states[-1]
            assert state.response_create_sent_at is None
            assert state.api_key_reservation is None
            assert state.response_create_admission is None
            assert state.account_response_create_lease is None
            assert not state.response_create_gate_acquired
            assert reservations_released == ["unsent-reservation"]
            assert not route.first.closed
            assert len(route.first.sent_text) == 1

            async def finish():
                route.first._messages.put_nowait(_websocket_response_batch("resp_a")[-1])

            client.portal.call(finish)
            assert websocket.receive_json()["type"] == "response.completed"
            armed = False
            assert complete_turn(websocket, "retry")["response"]["id"] == "resp_retry"
    assert route.connected == ["account_a"]
    assert len(route.first.sent_text) == 2
    assert not route.health_writes


def test_model_rejection_preserves_accepted_sibling(app_instance, route):
    route.first._deferred_message_batches.clear()
    route.first._deferred_message_batches.append(_websocket_response_batch("resp_a", completed=False))
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect("/v1/responses") as websocket:
            websocket.send_json(_websocket_response_create("accepted"))
            assert websocket.receive_json()["type"] == "response.created"
            client.portal.call(reject_model)
            websocket.send_json(_websocket_response_create("excluded"))
            assert websocket.receive_json()["response"]["error"]["code"] == "upstream_unavailable"
            assert not route.first.closed
            assert len(route.first.sent_text) == 1

            async def finish():
                route.first._messages.put_nowait(_websocket_response_batch("resp_a")[-1])

            client.portal.call(finish)
            assert websocket.receive_json()["type"] == "response.completed"
    assert not route.health_writes


@pytest.mark.parametrize("expired", [False, True])
def test_unrelated_or_expired_model_rejection_keeps_socket_reusable(app_instance, route, expired):
    route.first._deferred_message_batches.append(_websocket_response_batch("resp_unrelated"))
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect("/v1/responses") as websocket:
            complete_turn(websocket, "first")
            client.portal.call(reject_model, "gpt-5.4" if expired else "another-model")
            if expired:

                async def expire():
                    async with SessionLocal() as session:
                        await session.execute(
                            update(AccountPlanCheck).values(requested_at=utcnow() - timedelta(minutes=3))
                        )
                        await session.commit()

                client.portal.call(expire)
            assert complete_turn(websocket, "unrelated")["response"]["id"] == "resp_unrelated"
    assert route.connected == ["account_a"]
    assert not route.health_writes


def test_model_rejection_during_create_lease_wait_releases_unsent_turn(app_instance, route, monkeypatch):
    acquire_original = proxy_module.ProxyService._acquire_account_response_create_lease_or_overload
    calls = 0

    async def acquire(self, **kwargs):
        nonlocal calls
        calls += 1
        lease = await acquire_original(self, **kwargs)
        if calls == 2:
            await reject_model()
        return lease

    monkeypatch.setattr(proxy_module.ProxyService, "_acquire_account_response_create_lease_or_overload", acquire)
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect("/v1/responses") as websocket:
            complete_turn(websocket, "first")
            websocket.send_json(_websocket_response_create("excluded during admission"))
            assert websocket.receive_json()["response"]["error"]["code"] == "upstream_unavailable"
            state = route.states[-1]
            assert state.response_create_sent_at is None
            assert state.response_create_admission is None
            assert state.account_response_create_lease is None
            assert not state.response_create_gate_acquired
            assert len(route.first.sent_text) == 1
            assert complete_turn(websocket, "retry")["response"]["id"] == "resp_b"
    assert not route.health_writes


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize(
    "status", [AccountStatus.PAUSED, AccountStatus.REAUTH_REQUIRED, AccountStatus.DEACTIVATED, None]
)
def test_unavailable_idle_websocket_reselects_without_reusing_old_account(app_instance, route, path, status):
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect(path) as websocket:
            complete_turn(websocket, "first")
            client.portal.call(route.change_status, status)
            completed = complete_turn(websocket, "fresh")
            assert completed["response"]["id"] == "resp_b"
            assert route.first.closed
            assert len(route.first.sent_text) == len(route.second.sent_text) == 1
    assert route.connected == ["account_a", "account_b"]
    assert not route.health_writes


def test_dashboard_pause_rejects_anchored_followup_on_existing_socket(app_instance, route):
    with TestClient(app_instance, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect("/v1/responses") as websocket:
            complete_turn(websocket, "first")
            assert client.post("/api/accounts/account_a/pause").status_code == 200
            client.portal.call(route.availability.refresh_from_db)
            payload = _websocket_response_create("continue")
            payload["previous_response_id"] = "resp_a"
            websocket.send_json(payload)
            error = websocket.receive_json()
            assert error["type"] == "error"
            assert error["error"]["code"] == "previous_response_owner_unavailable"
            assert route.first.closed
            assert len(route.first.sent_text) == 1
            assert route.second.sent_text == []
    assert route.connected == ["account_a"]
    assert not route.health_writes


def test_pause_rejects_new_turn_without_interrupting_accepted_sibling(app_instance, route):
    route.first._deferred_message_batches.clear()
    route.first._deferred_message_batches.append(_websocket_response_batch("resp_a", completed=False))
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect("/v1/responses") as websocket:
            websocket.send_json(_websocket_response_create("in flight"))
            assert websocket.receive_json()["type"] == "response.created"
            client.portal.call(route.change_status, AccountStatus.PAUSED)
            websocket.send_json(_websocket_response_create("must not be sent"))
            error = websocket.receive_json()
            assert error["response"]["error"]["code"] == "upstream_unavailable"
            assert not route.first.closed
            assert len(route.first.sent_text) == 1

            async def finish():
                route.first._messages.put_nowait(_websocket_response_batch("resp_a")[-1])

            client.portal.call(finish)
            assert websocket.receive_json()["type"] == "response.completed"
            complete_turn(websocket, "now movable")
    assert route.connected == ["account_a", "account_b"]
    assert any(log.get("error_code") == "upstream_unavailable" for log in route.logs)
    assert not route.health_writes


@pytest.mark.parametrize("failure_hook", ["_write_websocket_connect_failure", "_emit_websocket_terminal_error"])
def test_pause_rejection_cancellation_keeps_unsent_cleanup_owned(app_instance, route, monkeypatch, failure_hook):
    original_acquire = proxy_module.ProxyService._acquire_account_response_create_lease_or_overload
    original_proxy = proxy_module.ProxyService.proxy_responses_websocket
    finished = Event()
    calls = 0

    async def acquire(self, **kwargs):
        nonlocal calls
        calls += 1
        lease = await original_acquire(self, **kwargs)
        if calls == 2:
            await route.change_status(AccountStatus.PAUSED)
        return lease

    async def fail_rejection(self, *args, **kwargs):
        raise asyncio.CancelledError("injected local rejection cancellation")

    async def proxy(self, *args, **kwargs):
        try:
            await original_proxy(self, *args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(proxy_module.ProxyService, "_acquire_account_response_create_lease_or_overload", acquire)
    monkeypatch.setattr(proxy_module.ProxyService, "proxy_responses_websocket", proxy)
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with suppress(FutureCancelledError):
            with client.websocket_connect("/v1/responses") as websocket:
                complete_turn(websocket, "first")
                monkeypatch.setattr(proxy_module.ProxyService, failure_hook, fail_rejection)
                websocket.send_json(_websocket_response_create("pause during admission"))
                assert finished.wait(timeout=10)
    state = route.states[-1]
    assert state.response_create_sent_at is None
    assert state.response_create_admission is None
    assert state.account_response_create_lease is None
    assert not state.response_create_gate_acquired
    assert len(route.first.sent_text) == 1
    assert not route.health_writes


def test_pause_during_create_lease_wait_releases_unsent_request(app_instance, route, monkeypatch):
    original_acquire = proxy_module.ProxyService._acquire_account_response_create_lease_or_overload
    reservations_released = []
    calls = 0

    async def acquire(self, **kwargs):
        nonlocal calls
        calls += 1
        lease = await original_acquire(self, **kwargs)
        if calls == 2:
            state = route.states[-1]
            state.api_key_reservation = ApiKeyUsageReservationData("unsent-reservation", "key", "gpt-5.4")
            await route.change_status(AccountStatus.PAUSED)
        return lease

    async def release_reservation(self, reservation):
        if reservation is not None:
            reservations_released.append(reservation.reservation_id)

    monkeypatch.setattr(proxy_module.ProxyService, "_acquire_account_response_create_lease_or_overload", acquire)
    monkeypatch.setattr(proxy_module.ProxyService, "_release_websocket_reservation", release_reservation)
    with TestClient(app_instance) as client:
        assert client.portal is not None
        client.portal.call(route.seed)
        with client.websocket_connect("/v1/responses") as websocket:
            complete_turn(websocket, "first")
            websocket.send_json(_websocket_response_create("pause during admission"))
            error = websocket.receive_json()
            assert error["response"]["error"]["code"] == "upstream_unavailable"
            state = route.states[-1]
            assert state.response_create_sent_at is None
            assert state.api_key_reservation is None
            assert state.response_create_admission is None
            assert state.account_response_create_lease is None
            assert not state.response_create_gate_acquired
            assert len(route.first.sent_text) == 1
            complete_turn(websocket, "gate was released")
    assert reservations_released == ["unsent-reservation"]
    assert any(log.get("error_code") == "upstream_unavailable" for log in route.logs)
    assert not route.health_writes
