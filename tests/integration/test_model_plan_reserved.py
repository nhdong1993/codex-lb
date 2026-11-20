"""Route-level coverage: a key's reserved accounts skip the subscription model Plan restriction."""

from __future__ import annotations

import itertools
from contextlib import asynccontextmanager
from functools import partial
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

import app.modules.proxy.load_balancer as load_balancer_module
import app.modules.proxy.service as proxy_module
from app.core.clients.proxy import ProxyResponseError
from app.core.openai.models import CompactResponsePayload
from app.db.models import Account
from app.db.session import SessionLocal
from app.dependencies import get_proxy_service_for_app
from app.modules.proxy import model_admission
from app.modules.proxy._service.http_bridge import request_submit
from app.modules.proxy.account_cache import get_account_selection_cache
from app.modules.usage import plan_checks
from tests.integration.test_proxy_transient_retry import _import_account, _success_sse_event
from tests.integration.test_proxy_websocket_responses import (
    _FakeUpstreamWebSocket,
    _websocket_response_batch,
    _websocket_response_create,
)

pytestmark = pytest.mark.integration
MODEL = "gpt-6-luna"
_inputs = itertools.count()
_SETTINGS = {"modelPlanRoutingPolicies": {MODEL: ["free"]}, "apiKeyAuthEnabled": True, "stickyThreadsEnabled": False}


async def _set(account_id: str, **values: Any) -> None:
    async with SessionLocal() as session:
        await session.execute(update(Account).where(Account.id == account_id).values(**values))
        await session.commit()
    get_account_selection_cache().invalidate()


@pytest.fixture
async def pool(async_client, app_instance, monkeypatch):
    """R=Plus reserved for key K, S=Free shared; the model is restricted to Free."""
    ids = {}
    for name, plan in (("r", "plus"), ("s", "free")):
        ids[name] = await _import_account(async_client, f"acc-{name}", f"{name}@example.com")
        await _set(ids[name], plan_type=plan)
    saved = await async_client.put(
        "/api/settings",
        json=_SETTINGS,
    )
    assert saved.status_code == 200, saved.text
    owner = (await async_client.post("/api/api-keys/", json={"name": "owner", "reservedAccountIds": [ids["r"]]})).json()
    other = (await async_client.post("/api/api-keys/", json={"name": "other"})).json()
    seen: list[str] = []

    async def stream(payload, headers, access_token, account_id, **kwargs):
        seen.append(account_id)
        yield _success_sse_event()

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    return SimpleNamespace(
        ids=ids,
        owner={"Authorization": f"Bearer {owner['key']}"},
        owner_id=owner["id"],
        other={"Authorization": f"Bearer {other['key']}"},
        other_id=other["id"],
        seen=seen,
        service=get_proxy_service_for_app(app_instance),
    )


async def _stream(async_client, headers: dict[str, str], **extra: Any) -> str:
    # A distinct input per call keeps prompt-cache affinity from pinning a later fresh request.
    payload = {"model": MODEL, "input": f"hello {next(_inputs)}", "stream": True, **extra}
    response = await async_client.post("/v1/responses", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.text


async def test_owner_key_uses_reserved_account_and_other_keys_keep_the_restriction(async_client, pool):
    assert "response.completed" in await _stream(async_client, pool.owner)
    assert "response.completed" in await _stream(async_client, pool.other)

    assert pool.seen == ["acc-r", "acc-s"]


async def test_lookup_miss_continuation_stays_in_the_restricted_pool(async_client, pool):
    text = await _stream(async_client, pool.owner, previous_response_id="resp_owner_not_recorded")

    assert "response.completed" in text
    assert pool.seen == ["acc-s"]
    assert "response.completed" in await _stream(async_client, pool.owner)
    assert pool.seen == ["acc-s", "acc-r"]


async def test_lookup_miss_continuation_with_only_the_reserved_account_sends_nothing(async_client, pool):
    await _set(pool.ids["s"], plan_type="plus")

    text = await _stream(async_client, pool.owner, previous_response_id="resp_owner_not_recorded")

    assert "previous_response_owner_unavailable" in text
    assert pool.seen == []


async def test_lookup_miss_continuation_ignores_a_reservation_granted_after_the_count(async_client, pool, monkeypatch):
    # A positive TTL keeps the warmed shared entry unless the grant endpoint invalidates it.
    monkeypatch.setattr(get_account_selection_cache(), "_ttl_seconds", 60)
    reserve = f"/api/api-keys/{pool.owner_id}"
    assert (await async_client.patch(reserve, json={"reservedAccountIds": []})).status_code == 200
    assert "response.completed" in await _stream(async_client, pool.owner)
    assert pool.seen == ["acc-s"]
    original = load_balancer_module.LoadBalancer._load_selection_inputs
    granted = False

    async def grant_after_first_load(self, **kwargs):
        nonlocal granted
        result = await original(self, **kwargs)
        if not granted:
            granted = True
            response = await async_client.patch(reserve, json={"reservedAccountIds": [pool.ids["r"]]})
            assert response.status_code == 200, response.text
        return result

    monkeypatch.setattr(load_balancer_module.LoadBalancer, "_load_selection_inputs", grant_after_first_load)
    assert "response.completed" in await _stream(async_client, pool.owner, previous_response_id="resp_unrecorded")
    assert pool.seen == ["acc-s", "acc-s"]

    assert "response.completed" in await _stream(async_client, pool.owner)
    assert pool.seen == ["acc-s", "acc-s", "acc-r"]


async def test_lookup_miss_dispatch_rechecks_without_the_exemption(async_client, pool, monkeypatch):
    # Only R is routable (Free, reserved for K); the request's own refresh then records Plus.
    await _set(pool.ids["s"], plan_type="plus")
    await _set(pool.ids["r"], plan_type="free")
    original = proxy_module.ProxyService._ensure_fresh_with_budget

    async def refresh_records_plus(self, target, **kwargs):
        refreshed = await original(self, target, **kwargs)
        await _set(target.id, plan_type="plus")
        return refreshed

    monkeypatch.setattr(proxy_module.ProxyService, "_ensure_fresh_with_budget", refresh_records_plus)
    response = await async_client.post(
        "/v1/responses",
        json={"model": MODEL, "input": "refresh", "stream": True, "previous_response_id": "resp_unrecorded"},
        headers=pool.owner,
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"
    assert pool.seen == []
    assert "response.completed" in await _stream(async_client, pool.owner)
    assert pool.seen == ["acc-r"]


@pytest.mark.parametrize(
    ("request_key", "owner", "plan", "admitted"),
    [
        (None, None, "plus", False),
        (None, "K", "plus", False),
        ("K", "K", "plus", True),
        ("K", None, "plus", False),
        ("K", "J", "plus", False),
        ("J", "K", "plus", False),
        ("K", "J", "free", True),
        (None, "K", "free", True),
    ],
)
async def test_admission_reads_the_reservation_with_the_plan(async_client, pool, request_key, owner, plan, admitted):
    keys = {"K": pool.owner_id, "J": pool.other_id, None: None}
    await _set(pool.ids["r"], plan_type=plan, reserved_api_key_id=keys[owner])
    account = cast(Any, SimpleNamespace(id=pool.ids["r"]))

    rejected = await model_admission.policy_rejected_account_ids([account], MODEL, keys[request_key])

    assert (pool.ids["r"] not in rejected) is admitted


async def test_policy_recheck_for_an_unmapped_model_skips_plan_checks_and_account_reads(pool, monkeypatch):
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("no account read or plan check for an unmapped model")

    monkeypatch.setattr(plan_checks, "rejected_model_account_ids", forbidden)
    monkeypatch.setattr(model_admission, "get_background_session", forbidden)

    assert (
        await model_admission.policy_rejected_account_ids([cast(Any, SimpleNamespace(id="x"))], "gpt-unmapped", "K")
        == set()
    )


class _Session:
    def __init__(self, account: Any, api_key_id: str | None, pending: list[Any]) -> None:
        self.account = account
        self.key = SimpleNamespace(api_key_id=api_key_id)
        self.pending_requests = pending

        @asynccontextmanager
        async def _lock():
            yield

        self.pending_lock = _lock()


def _request(model: str, *, attached: bool = True, deadline: float = 1_000.0) -> Any:
    return SimpleNamespace(
        model=model,
        event_queue=object() if attached else None,
        draining_until_terminal=not attached,
        bridge_request_deadline=deadline,
        started_at=0.0,
    )


class _Clock:
    def __init__(self, now: float) -> None:
        self.now = now

    def monotonic(self) -> float:
        return self.now


async def test_bridge_resend_gate_applies_to_keyed_sessions_whatever_the_account_snapshot(monkeypatch):
    calls: list[tuple[str | None, str | None]] = []

    async def policy(accounts, model, api_key_id):
        calls.append((model, api_key_id))
        return {accounts[0].id} if model == "restricted" else set()

    monkeypatch.setattr(model_admission, "policy_rejected_account_ids", policy)
    clock = _Clock(10.0)

    def gate(api_key_id: str | None, request: Any) -> Any:
        # The snapshot says "released"; the policy read, not the snapshot, decides.
        session = _Session(SimpleNamespace(id="r", reserved_api_key_id=None), api_key_id, [request])
        return request_submit._http_bridge_resend_refusal(cast(Any, session), request, clock=cast(Any, clock))

    # Keyless session: existing path, no lookup.
    assert await gate(None, _request("restricted")) is None
    assert calls == []
    # Keyed session: the frame's own model decides, after the wait.
    assert isinstance(await gate("K", _request("restricted")), ProxyResponseError)
    assert await gate("K", _request("allowed")) is None
    assert calls[-1] == ("allowed", "K")
    # Policy allows, but the consumer detached or the deadline passed during the lookup.
    assert isinstance(await gate("K", _request("allowed", attached=False)), ProxyResponseError)
    assert isinstance(await gate("K", _request("allowed", deadline=5.0)), ProxyResponseError)


class _NoLockWait:
    """The resend gate must not wait on the session lock after its policy read."""

    async def __aenter__(self) -> None:
        raise AssertionError("no lock wait may follow the policy read")

    async def __aexit__(self, *_exc: object) -> None:
        return None


@pytest.mark.parametrize("change", ["unchanged", "release_reservation", "restrict_plan"])
async def test_bridge_resend_reads_the_policy_last_after_a_release_or_plan_change(async_client, pool, change):
    if change == "unchanged":
        response = SimpleNamespace(status_code=200, text="")
        account_id, key_id = pool.ids["r"], pool.owner_id
    elif change == "release_reservation":
        # K's Plus R was admitted through the exemption; the reservation is released through the API.
        response = await async_client.patch(f"/api/api-keys/{pool.owner_id}", json={"reservedAccountIds": []})
        account_id, key_id = pool.ids["r"], pool.owner_id
    else:
        # Shared Free S was admitted; the operator restricts the model to Plus through the API.
        response = await async_client.put("/api/settings", json={"modelPlanRoutingPolicies": {MODEL: ["plus"]}})
        account_id, key_id = pool.ids["s"], pool.other_id
    assert response.status_code == 200, response.text
    request = _request(MODEL, deadline=float("inf"))
    session = _Session(SimpleNamespace(id=account_id), key_id, [request])
    session.pending_lock = _NoLockWait()

    refusal = await request_submit._http_bridge_resend_refusal(cast(Any, session), request, clock=_Clock(0.0))

    if change == "unchanged":
        # Admitted with no lock wait after the read (the lock raises if entered).
        assert refusal is None
        return
    assert isinstance(refusal, ProxyResponseError)
    assert refusal.status_code == 503


def _compact_payload(**extra: Any) -> dict[str, Any]:
    # A distinct input per call keeps prompt-cache affinity from pinning a later fresh request.
    return {"model": MODEL, "instructions": "", "input": f"compact {next(_inputs)}", **extra}


@pytest.fixture
def compact_seen(monkeypatch):
    seen: list[str] = []

    async def compact(payload, headers, access_token, account_id, **kwargs):
        seen.append(account_id)
        return CompactResponsePayload.model_validate(
            {
                "object": "response.compaction",
                "compaction_summary": {"id": "cmp_reserved", "encrypted_content": "summary"},
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }
        )

    monkeypatch.setattr(proxy_module, "core_compact_responses", compact)
    return seen


async def test_compact_lookup_miss_stays_in_the_restricted_pool(async_client, pool, compact_seen):
    miss = _compact_payload(previous_response_id="resp_owner_not_recorded")
    response = await async_client.post("/v1/responses/compact", json=miss, headers=pool.owner)
    assert response.status_code == 200, response.text
    response = await async_client.post("/v1/responses/compact", json=_compact_payload(), headers=pool.owner)
    assert response.status_code == 200, response.text

    assert compact_seen == ["acc-s", "acc-r"]


async def test_compact_lookup_miss_with_only_the_reserved_account_sends_nothing(async_client, pool, compact_seen):
    await _set(pool.ids["s"], plan_type="plus")

    miss = _compact_payload(previous_response_id="resp_owner_not_recorded")
    response = await async_client.post("/v1/responses/compact", json=miss, headers=pool.owner)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "previous_response_owner_unavailable"
    assert compact_seen == []


@pytest.fixture
def ws_route(app_instance, monkeypatch):
    """The same R/S pool, set up through a sync TestClient for direct WebSocket turns."""
    opened: list[str] = []

    async def open_attempt(self, account, headers, **kwargs):
        opened.append(account.id)
        return account, _FakeUpstreamWebSocket(_websocket_response_batch(f"resp_ws_{len(opened)}"))

    monkeypatch.setattr(proxy_module.ProxyService, "_try_open_websocket_connect_attempt", open_attempt)

    async def setup() -> tuple[dict[str, str], dict[str, Any]]:
        # Dashboard writes go through the same in-process ASGI client as ``async_client``.
        async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://testserver") as api:
            ids = {}
            for name, plan in (("r", "plus"), ("s", "free")):
                ids[name] = await _import_account(api, f"acc-{name}", f"{name}@example.com")
                await _set(ids[name], plan_type=plan)
            assert (await api.put("/api/settings", json=_SETTINGS)).status_code == 200
            owner = await api.post("/api/api-keys/", json={"name": "owner", "reservedAccountIds": [ids["r"]]})
            return ids, owner.json()

    with TestClient(app_instance, client=("127.0.0.1", 50000)) as client:
        assert client.portal is not None
        ids, owner = client.portal.call(setup)
        yield SimpleNamespace(client=client, ids=ids, opened=opened, owner={"Authorization": f"Bearer {owner['key']}"})


def _ws_turn(route: Any, **extra: Any) -> list[dict[str, Any]]:
    payload = {**_websocket_response_create(f"ws {next(_inputs)}"), "model": MODEL, **extra}
    with route.client.websocket_connect("/v1/responses", headers=route.owner) as websocket:
        websocket.send_json(payload)
        first = websocket.receive_json()
        return [first] if first["type"] == "error" else [first, websocket.receive_json()]


def test_websocket_lookup_miss_stays_in_the_restricted_pool(ws_route):
    events = _ws_turn(ws_route, previous_response_id="resp_owner_not_recorded")
    assert events[-1]["type"] == "response.completed"
    assert _ws_turn(ws_route)[-1]["type"] == "response.completed"

    assert ws_route.opened == [ws_route.ids["s"], ws_route.ids["r"]]


def test_websocket_lookup_miss_with_only_the_reserved_account_sends_nothing(ws_route):
    ws_route.client.portal.call(partial(_set, ws_route.ids["s"], plan_type="plus"))

    events = _ws_turn(ws_route, previous_response_id="resp_owner_not_recorded")

    # The direct WebSocket keeps its existing no-candidate envelope.
    assert events[-1]["type"] == "error"
    assert events[-1]["error"]["code"] == "no_accounts"
    assert ws_route.opened == []
