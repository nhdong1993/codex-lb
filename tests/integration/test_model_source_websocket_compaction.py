"""Codex compaction turns on Responses WebSocket source sessions."""

from __future__ import annotations

from typing import Any

import pytest
from aiohttp import web
from sqlalchemy import select

from app.core.clients.proxy import ProxyResponseError
from app.core.errors import openai_error
from app.db.models import ApiKeyUsageReservation
from app.db.session import SessionLocal
from app.modules.proxy.service import ProxyService
from app.modules.proxy.source_admission import get_source_bulkhead
from tests.integration.model_source_helpers import stub_source_upstreams
from tests.integration.test_model_source_websocket import complete, create_key, create_source, websocket_client
from tests.integration.test_model_source_websocket_http_bridge import (
    MESSAGE,
    ROUTE_CONTINUITY_CODES,
    USER_MESSAGE,
    _envelope,
    _receive_turn,
    _rows,
    _sse,
    _turn_events,
)
from tests.integration.test_proxy_transient_retry import _import_account

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

ROUTES = ["/v1/responses", "/backend-api/codex/responses"]
TRIGGER: dict[str, Any] = {"type": "compaction_trigger"}
COMPACTION: dict[str, Any] = {"type": "compaction", "id": "cmp_1", "encrypted_content": "opaque-compaction"}


def _compaction_events(response_id: str) -> list[dict[str, Any]]:
    return [
        {"type": "response.created", "response": _envelope(response_id, "in_progress", [])},
        {"type": "response.output_item.added", "output_index": 0, "item": COMPACTION},
        {"type": "response.output_item.done", "output_index": 0, "item": COMPACTION},
        {"type": "response.completed", "response": _envelope(response_id, "completed", [COMPACTION], usage=True)},
    ]


@pytest.fixture
def subscription_calls(monkeypatch) -> list[Any]:
    calls: list[Any] = []

    async def subscription_prepare(self, payload, **kwargs):
        calls.append(payload)
        raise ProxyResponseError(409, openai_error("subscription_probe", "Local subscription fixture"))

    monkeypatch.setattr(ProxyService, "_prepare_websocket_response_create_request", subscription_prepare)
    return calls


async def _reservations() -> list[ApiKeyUsageReservation]:
    async with SessionLocal() as session:
        return list((await session.execute(select(ApiKeyUsageReservation))).scalars().all())


@pytest.mark.parametrize("path", ROUTES)
async def test_first_turn_compaction_reaches_http_only_source(async_client, app_instance, subscription_calls, path):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse(request, _compaction_events("resp_compact"))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, path, key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [USER_MESSAGE, TRIGGER]})
            events = await _receive_turn(ws)
        rows, reservations = await _rows(source_id)
    assert not subscription_calls
    assert events[-1]["type"] == "response.completed", events
    assert events[-1]["response"]["model"] == "source-ws-model"
    assert [event["item"] for event in events if event["type"] == "response.output_item.done"] == [COMPACTION]
    assert len(bodies) == 1
    assert bodies[0]["stream"] is True
    assert bodies[0]["input"] == [USER_MESSAGE, TRIGGER]
    assert not {"type", "generate", "previous_response_id"} & bodies[0].keys()
    assert [(row.transport, row.upstream_transport, row.request_kind, row.status) for row in rows] == [
        ("websocket", "openai_compatible_http", "compaction", "success")
    ]
    assert [reservation.status for reservation in reservations] == ["finalized"]
    assert get_source_bulkhead().in_flight(source_id) == 0


@pytest.mark.parametrize("path", ROUTES)
async def test_compaction_continues_bound_bridged_session(async_client, app_instance, subscription_calls, path):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        if len(bodies) == 1:
            return await _sse(request, _turn_events("resp_1", [MESSAGE]))
        return await _sse(request, _compaction_events("resp_compact"))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, path, key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [USER_MESSAGE]})
            first = await _receive_turn(ws)
            assert first[-1]["type"] == "response.completed", first
            await ws.send(
                {
                    "type": "response.create",
                    "model": "source-ws-model",
                    "previous_response_id": "resp_1",
                    "input": [TRIGGER],
                }
            )
            second = await _receive_turn(ws)
        rows, _ = await _rows(source_id)
    assert not subscription_calls
    assert second[-1]["type"] == "response.completed", second
    assert len(bodies) == 2
    # ``ResponsesRequest`` normalization omits the empty annotations list.
    replayed_message = {**MESSAGE, "content": [{"type": "output_text", "text": "done"}]}
    assert bodies[1]["input"] == [USER_MESSAGE, replayed_message, TRIGGER]
    assert "previous_response_id" not in bodies[1]
    assert [(row.request_kind, row.status) for row in rows] == [("normal", "success"), ("compaction", "success")]


@pytest.mark.parametrize("path", ROUTES)
async def test_bridged_compaction_response_is_not_continuable(async_client, app_instance, subscription_calls, path):
    bodies: list[dict[str, Any]] = []
    follow_up: dict[str, Any] = {"role": "user", "content": "Continue after compaction"}

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        if len(bodies) == 1:
            return await _sse(request, _compaction_events("resp_compact"))
        return await _sse(request, _turn_events("resp_after", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, path, key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [USER_MESSAGE, TRIGGER]})
            compacted = await _receive_turn(ws)
            assert compacted[-1]["type"] == "response.completed", compacted
            await ws.send(
                {
                    "type": "response.create",
                    "model": "source-ws-model",
                    "previous_response_id": "resp_compact",
                    "input": [follow_up],
                }
            )
            refused = await ws.receive()
        # The bound session ends on the continuity error; Codex reconnects and
        # resends its compacted history in full.
        async with websocket_client(app_instance, path, key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [COMPACTION, follow_up]})
            resent = await _receive_turn(ws)
        rows, reservations = await _rows(source_id)
    assert refused["type"] == "error", refused
    assert refused["status"] == 502
    assert refused["error"]["code"] == ROUTE_CONTINUITY_CODES[path]
    assert resent[-1]["type"] == "response.completed", resent
    assert not subscription_calls
    assert len(bodies) == 2
    assert bodies[1]["input"][0]["type"] == "compaction"
    assert bodies[1]["input"][-1] == follow_up
    assert TRIGGER not in bodies[1]["input"]
    assert [(row.request_kind, row.status) for row in rows] == [("compaction", "success"), ("normal", "success")]
    assert [reservation.status for reservation in reservations] == ["finalized", "finalized"]


@pytest.mark.parametrize("path", ROUTES)
async def test_native_source_session_serves_compaction(async_client, app_instance, subscription_calls, path):
    frames: list[dict[str, Any]] = []

    async def provider(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        frames.append(await ws.receive_json())
        await complete(ws, response_id="resp_native_compact")
        async for _ in ws:
            pass
        return ws

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(provider, shutdown_timeout=1))
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, path, key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [USER_MESSAGE, TRIGGER]})
            events = await _receive_turn(ws)
        rows, _ = await _rows(source_id)
    assert not subscription_calls
    assert events[-1]["type"] == "response.completed", events
    assert len(frames) == 1
    assert frames[0]["input"][-1] == TRIGGER
    assert [(row.upstream_transport, row.request_kind) for row in rows] == [
        ("openai_compatible_websocket", "compaction")
    ]


@pytest.mark.parametrize("path", ROUTES)
async def test_compaction_for_disabled_source_is_refused(async_client, app_instance, subscription_calls, path):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse(request, _compaction_events("resp_compact"))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        # A source-only key whose only source is off is refused at the
        # handshake; an assigned account keeps the upgrade open.
        account_id = await _import_account(async_client, "compact-disabled", "compact-disabled@example.test")
        response = await async_client.patch(f"/api/api-keys/{key['id']}", json={"assignedAccountIds": [account_id]})
        assert response.status_code == 200, response.text
        response = await async_client.patch(f"/api/model-sources/{source_id}", json={"isEnabled": False})
        assert response.status_code == 200, response.text
        async with websocket_client(app_instance, path, key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [USER_MESSAGE, TRIGGER]})
            event = await ws.receive()
    assert event["type"] == "error", event
    assert event["status"] == 503
    assert event["error"]["code"] == "model_source_disabled"
    assert not bodies
    assert not subscription_calls
    assert not await _reservations()
