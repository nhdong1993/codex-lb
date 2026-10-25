"""Client Responses WebSocket bridged to an HTTP/SSE-only model source."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from aiohttp import web
from sqlalchemy import select, update

from app.db.models import ApiKeyUsageReservation, ModelSourceModel, RequestLog
from app.db.session import SessionLocal
from app.modules.proxy.source_admission import get_source_bulkhead
from app.modules.proxy.source_dispatch import SourceDispatch
from tests.integration.model_source_helpers import _create_model_source, stub_source_upstreams
from tests.integration.test_model_source_websocket import create_key, create_source, websocket_client

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

ROUTE_CONTINUITY_CODES = {
    "/v1/responses": "stream_incomplete",
    "/backend-api/codex/responses": "previous_response_not_found",
}
USER_MESSAGE: dict[str, Any] = {
    "type": "message",
    "role": "user",
    "content": [{"type": "input_text", "text": "run the tool"}],
}
REASONING: dict[str, Any] = {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "opaque-reasoning"}
FUNCTION_CALL: dict[str, Any] = {
    "type": "function_call",
    "id": "fc_1",
    "call_id": "call_1",
    "name": "shell",
    "arguments": "{}",
    "status": "completed",
}
TOOL_OUTPUT: dict[str, Any] = {"type": "function_call_output", "call_id": "call_1", "output": "ok"}
MESSAGE: dict[str, Any] = {
    "type": "message",
    "id": "msg_2",
    "role": "assistant",
    "status": "completed",
    "content": [{"type": "output_text", "text": "done", "annotations": []}],
}


def _envelope(response_id: str, status: str, output: list[dict[str, Any]], *, usage: bool = False):
    envelope: dict[str, Any] = {
        "id": response_id,
        "object": "response",
        "model": "source-ws-model",
        "status": status,
        "output": output,
    }
    if usage:
        envelope["usage"] = {"input_tokens": 11, "output_tokens": 5, "total_tokens": 16}
    return envelope


def _turn_events(response_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [{"type": "response.created", "response": _envelope(response_id, "in_progress", [])}]
    for index, item in enumerate(items):
        events.append({"type": "response.output_item.added", "output_index": index, "item": item})
        events.append({"type": "response.output_item.done", "output_index": index, "item": item})
    events.append({"type": "response.completed", "response": _envelope(response_id, "completed", items, usage=True)})
    return events


async def _sse(request: web.Request, events: list[dict[str, Any]], *, noise: bool = False) -> web.StreamResponse:
    response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
    await response.prepare(request)
    if noise:
        await response.write(b": keepalive\n\n")
        await response.write(b'event: codex.rate_limits\ndata: {"type":"codex.rate_limits","primary":{}}\n\n')
    for event in events:
        await response.write(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode())
    await response.write(b"data: [DONE]\n\n")
    await response.write_eof()
    return response


async def _receive_turn(ws) -> list[dict[str, Any]]:
    events = []
    while True:
        event = await ws.receive()
        events.append(event)
        if event["type"] in {"response.completed", "response.failed", "response.incomplete", "error"}:
            return events


async def _rows(source_id: str) -> tuple[list[RequestLog], list[ApiKeyUsageReservation]]:
    async with SessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(RequestLog).where(RequestLog.model_source_id == source_id).order_by(RequestLog.id)
                )
            )
            .scalars()
            .all()
        )
        reservations = (
            (await session.execute(select(ApiKeyUsageReservation).order_by(ApiKeyUsageReservation.created_at)))
            .scalars()
            .all()
        )
    return list(rows), list(reservations)


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses/"])
@pytest.mark.parametrize("scope", ["source_only", "mixed"])
async def test_bridge_tool_continuation_rebuilds_full_input(async_client, app_instance, path, scope):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        if len(bodies) == 1:
            return await _sse(request, _turn_events("resp_1", [REASONING, FUNCTION_CALL]), noise=True)
        return await _sse(request, _turn_events("resp_2", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        if scope == "mixed":
            from tests.integration.test_proxy_transient_retry import _import_account

            account_id = await _import_account(async_client, "bridge-mixed", "bridge-mixed@example.test")
            response = await async_client.patch(f"/api/api-keys/{key['id']}", json={"assignedAccountIds": [account_id]})
            assert response.status_code == 200, response.text
        async with websocket_client(app_instance, path, key["key"]) as ws:
            await ws.send(
                {
                    "type": "response.create",
                    "model": "source-ws-model",
                    "input": [USER_MESSAGE],
                    "client_metadata": {"x-codex-turn-metadata": "{}"},
                }
            )
            first = await _receive_turn(ws)
            assert [event["type"] for event in first] == [
                "response.created",
                "response.output_item.added",
                "response.output_item.done",
                "response.output_item.added",
                "response.output_item.done",
                "response.completed",
            ]
            assert first[-1]["response"]["model"] == "source-ws-model"
            await ws.send(
                {
                    "type": "response.create",
                    "model": "source-ws-model",
                    "previous_response_id": "resp_1",
                    "input": [TOOL_OUTPUT],
                }
            )
            second = await _receive_turn(ws)
            assert second[-1]["type"] == "response.completed", second
        rows, reservations = await _rows(source_id)
    assert len(bodies) == 2
    for body in bodies:
        assert body["stream"] is True
        assert not {"type", "generate", "previous_response_id", "client_metadata"} & body.keys()
    assert bodies[0]["input"] == [USER_MESSAGE]
    assert bodies[1]["input"] == [USER_MESSAGE, REASONING, FUNCTION_CALL, TOOL_OUTPUT]
    assert [(row.transport, row.upstream_transport, row.status) for row in rows] == [
        ("websocket", "openai_compatible_http", "success")
    ] * 2
    assert [reservation.status for reservation in reservations] == ["finalized", "finalized"]
    assert get_source_bulkhead().in_flight(source_id) == 0


async def test_bridge_warmup_is_local_and_immediately_continuable(async_client, app_instance):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse(request, _turn_events("resp_after_warmup", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/backend-api/codex/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hello", "generate": False})
            created, completed = await ws.receive(), await ws.receive()
            assert created["type"] == "response.created"
            assert completed["type"] == "response.completed"
            warmup_id = completed["response"]["id"]
            assert warmup_id.startswith("resp_") and warmup_id == created["response"]["id"]
            assert completed["response"]["status"] == "completed"
            assert completed["response"]["output"] == []
            assert completed["response"]["model"] == "source-ws-model"
            assert "usage" not in completed["response"]
            await ws.send(
                {"type": "response.create", "model": "source-ws-model", "previous_response_id": warmup_id, "input": []}
            )
            turn = await _receive_turn(ws)
            assert turn[-1]["type"] == "response.completed", turn
        rows, reservations = await _rows(source_id)
    assert [body["input"] for body in bodies] == [[{"role": "user", "content": "hello"}]]
    assert len(rows) == 1 and rows[0].status == "success"
    assert [reservation.status for reservation in reservations] == ["finalized"]
    assert get_source_bulkhead().in_flight(source_id) == 0


@pytest.mark.parametrize("path", sorted(ROUTE_CONTINUITY_CODES))
async def test_bridge_unknown_previous_response_fails_closed(async_client, app_instance, path):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse(request, _turn_events("resp_known", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, path, key["key"]) as ws:
            # A first turn cannot continue connection-local state.
            await ws.send(
                {"type": "response.create", "model": "source-ws-model", "previous_response_id": "resp_x", "input": []}
            )
            event = await ws.receive()
            assert event["type"] == "error" and event["status"] == 502
            assert event["error"]["code"] == ROUTE_CONTINUITY_CODES[path]
            # The socket stays usable; after a completed turn, a stale anchor still fails.
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            assert (await _receive_turn(ws))[-1]["type"] == "response.completed"
            await ws.send(
                {"type": "response.create", "model": "source-ws-model", "previous_response_id": "resp_x", "input": []}
            )
            event = await ws.receive()
            assert event["error"]["code"] == ROUTE_CONTINUITY_CODES[path]
        rows, reservations = await _rows(source_id)
    assert len(bodies) == 1
    assert len(rows) == 1
    assert [reservation.status for reservation in reservations] == ["finalized"]


async def test_bridge_failed_response_is_sanitized_and_not_continuable(async_client, app_instance):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        if len(bodies) == 1:
            failed = _envelope("resp_failed", "failed", [])
            failed["error"] = {"code": "server_error", "message": "token-native leaked at https://private.example"}
            return await _sse(
                request,
                [
                    {"type": "response.created", "response": _envelope("resp_failed", "in_progress", [])},
                    {"type": "response.failed", "response": failed},
                ],
            )
        return await _sse(request, _turn_events("resp_ok", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            failed = (await _receive_turn(ws))[-1]
            assert failed["type"] == "response.failed"
            assert failed["response"]["error"]["code"] == "model_source_response_failed"
            assert "private.example" not in json.dumps(failed)
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "again"})
            assert (await _receive_turn(ws))[-1]["type"] == "response.completed"
            await ws.send(
                {
                    "type": "response.create",
                    "model": "source-ws-model",
                    "previous_response_id": "resp_failed",
                    "input": [],
                }
            )
            assert (await ws.receive())["error"]["code"] == "stream_incomplete"
        rows, reservations = await _rows(source_id)
    assert len(bodies) == 2
    assert [reservation.status for reservation in reservations] == ["released", "finalized"]
    assert [(row.status, row.upstream_error_code) for row in rows] == [("error", "server_error"), ("success", None)]
    assert "private.example" not in json.dumps({column: str(value) for column, value in vars(rows[0]).items()})


async def test_bridge_error_event_records_the_source_code_but_not_its_message(async_client, app_instance):
    async def handler(request: web.Request) -> web.StreamResponse:
        await request.json()
        return await _sse(
            request,
            [
                {"type": "response.created", "response": _envelope("resp_eof", "in_progress", [])},
                {
                    "type": "error",
                    "error": {
                        "type": "server_error",
                        "code": "upstream_eof",
                        "message": "token at https://private.example",
                    },
                },
            ],
        )

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            event = (await _receive_turn(ws))[-1]
            assert event["type"] == "error" and event["status"] == 502
            assert event["error"]["code"] == "model_source_response_failed"
            assert "private.example" not in json.dumps(event)
        rows, reservations = await _rows(source_id)
    assert [(row.status, row.error_code, row.upstream_error_code) for row in rows] == [
        ("error", "model_source_response_failed", "upstream_eof")
    ]
    assert "private.example" not in json.dumps({column: str(value) for column, value in vars(rows[0]).items()})
    assert [reservation.status for reservation in reservations] == ["released"]


async def test_bridge_turn_records_proxy_measured_timing(async_client, app_instance):
    async def handler(request: web.Request) -> web.StreamResponse:
        await request.json()
        streaming_message = {**MESSAGE, "status": "in_progress", "content": []}
        return await _sse(
            request,
            [
                {"type": "response.created", "response": _envelope("resp_timed", "in_progress", [])},
                {"type": "response.output_item.added", "output_index": 0, "item": streaming_message},
                {
                    "type": "response.output_text.delta",
                    "item_id": "msg_2",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": "done",
                },
                {"type": "response.output_item.done", "output_index": 0, "item": MESSAGE},
                {"type": "response.completed", "response": _envelope("resp_timed", "completed", [MESSAGE], usage=True)},
            ],
        )

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            assert (await _receive_turn(ws))[-1]["type"] == "response.completed"
        rows, _ = await _rows(source_id)
    assert [(row.transport, row.upstream_transport, row.status) for row in rows] == [
        ("websocket", "openai_compatible_http", "success")
    ]
    # The source sends no ``metrics``: the bridged turn is timed by the proxy.
    assert rows[0].latency_first_token_ms is not None and rows[0].latency_ms is not None
    assert rows[0].latency_first_token_ms <= rows[0].latency_ms


async def test_bridge_source_rejection_returns_http_envelope(async_client, app_instance):
    calls = 0

    async def handler(request: web.Request) -> web.Response:
        nonlocal calls
        calls += 1
        return web.json_response(
            {"error": {"type": "rate_limit_error", "code": "rate_limit_exceeded", "message": "slow down"}},
            status=429,
            headers={"Retry-After": "1"},
        )

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            event = await ws.receive()
        rows, reservations = await _rows(source_id)
    # A single portable source has no replacement: its own 429 is reported.
    assert event["type"] == "error" and event["status"] == 429, event
    assert event["error"]["code"] != "model_source_busy"
    assert calls == 1
    assert [reservation.status for reservation in reservations] == ["released"]
    assert [(row.status, row.failure_detail) for row in rows] == [
        ("error", "source_bridge events=none handed_off=none replay=none")
    ]
    assert get_source_bulkhead().in_flight(source_id) == 0


@pytest.mark.parametrize("second_status", [200, 503])
async def test_bridge_failover_and_exhausted_pool(async_client, app_instance, monkeypatch, second_status):
    from app.modules.proxy.source_pool import SourcePool

    calls: list[str] = []

    async def failing(request: web.Request) -> web.Response:
        calls.append("first")
        return web.json_response({"error": {"code": "server_error", "message": "down"}}, status=500)

    async def second(request: web.Request) -> web.StreamResponse:
        calls.append("second")
        if second_status != 200:
            return web.json_response({"error": {"code": "overloaded", "message": "busy"}}, status=second_status)
        return await _sse(request, _turn_events("resp_second", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(failing, shutdown_timeout=1), enabled=False)
        second_id = await _create_model_source(
            async_client,
            name="z-second",
            model="source-ws-model",
            base_url=await start(second, shutdown_timeout=1),
            supports_responses=True,
        )
        key = await create_key(async_client, source_id)
        await async_client.patch(f"/api/api-keys/{key['id']}", json={"assignedSourceIds": [source_id, second_id]})
        monkeypatch.setattr(
            SourcePool,
            "choose",
            lambda self, sources, *, excluded: next(
                (source for source in sorted(sources, key=lambda s: s.name) if source.id not in excluded), None
            ),
        )
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            last = (await _receive_turn(ws))[-1]
        _, reservations = await _rows(source_id)
    assert calls == ["first", "second"]
    if second_status == 200:
        assert last["type"] == "response.completed"
        assert [reservation.status for reservation in reservations] == ["released", "finalized"]
    else:
        # Exhausted pool: the last source error, not ``model_source_busy``.
        assert last["type"] == "error" and last["status"] == second_status, last
        assert [reservation.status for reservation in reservations] == ["released", "released"]


async def test_bridge_client_disconnect_closes_source_request(async_client, app_instance):
    entered, closed = asyncio.Event(), asyncio.Event()

    async def handler(request: web.Request) -> web.StreamResponse:
        await request.json()
        response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        created = {"type": "response.created", "response": _envelope("resp_live", "in_progress", [])}
        await response.write(f"data: {json.dumps(created)}\n\n".encode())
        delta = {"type": "response.output_text.delta", "item_id": "msg_live", "delta": "partial"}
        await response.write(f"data: {json.dumps(delta)}\n\n".encode())
        entered.set()
        try:
            while True:
                await asyncio.sleep(0.05)
                await response.write(b": waiting\n\n")
        except (ConnectionResetError, asyncio.CancelledError):
            closed.set()
            raise

    async with stub_source_upstreams() as start:
        url = await start(handler, handler_cancellation=True, shutdown_timeout=1)
        source_id = await create_source(async_client, url, enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            await asyncio.wait_for(entered.wait(), 5)
            assert (await ws.receive())["type"] == "response.created"
            assert (await ws.receive())["type"] == "response.output_text.delta"
        await asyncio.wait_for(closed.wait(), 5)
        rows, reservations = await _rows(source_id)
    assert [row.status for row in rows] == ["cancelled"]
    assert [reservation.status for reservation in reservations] == ["finalized"]
    assert get_source_bulkhead().in_flight(source_id) == 0


async def test_bridge_open_deadline_is_a_source_timeout(async_client, app_instance, monkeypatch):
    import app.modules.proxy.api as api
    from app.modules.proxy import source_websocket

    release = asyncio.Event()

    async def stall_headers(request: web.Request) -> web.Response:
        await request.json()
        await release.wait()
        return web.Response(status=500)

    async def lifecycle_held_off(self) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(source_websocket.SourceWebSocketSession, "_lifecycle", lifecycle_held_off)
    monkeypatch.setattr(api.proxy_service_module, "_stream_request_budget_seconds", lambda *args, **kwargs: 3.0)
    async with stub_source_upstreams() as start:
        url = await start(stall_headers, handler_cancellation=True, shutdown_timeout=1)
        source_id = await create_source(async_client, url, enabled=False)
        key = await create_key(async_client, source_id)
        try:
            async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
                await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
                event = await ws.receive()
        finally:
            release.set()
        rows, reservations = await _rows(source_id)
    assert event["type"] == "error" and event["status"] == 504, event
    assert event["error"]["code"] == "model_source_timeout"
    assert [(row.status, row.error_code) for row in rows] == [("error", "model_source_timeout")]
    assert [reservation.status for reservation in reservations] == ["released"]
    assert get_source_bulkhead().in_flight(source_id) == 0


async def test_bridge_prepared_warmup_released_without_dispatch_on_disconnect(async_client, app_instance, monkeypatch):
    from app.modules.proxy import source_websocket

    prepared = asyncio.Event()
    finished: list[str] = []
    calls = 0

    async def handler(request: web.Request) -> web.Response:
        nonlocal calls
        calls += 1
        return web.Response(status=500)

    async def blocked_warmup(self, turn) -> None:
        prepared.set()
        await asyncio.Event().wait()

    original_finish = SourceDispatch.finish

    async def spy_finish(self, **kwargs) -> None:
        finished.append(kwargs["status"])
        await original_finish(self, **kwargs)

    monkeypatch.setattr(source_websocket.SourceWebSocketSession, "_answer_local_warmup", blocked_warmup)
    monkeypatch.setattr(SourceDispatch, "finish", spy_finish)
    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi", "generate": False})
            await asyncio.wait_for(prepared.wait(), 5)
            assert get_source_bulkhead().in_flight(source_id) == 1
        rows, reservations = await _rows(source_id)
    assert calls == 0
    assert finished == []
    assert rows == [] and reservations == []
    assert get_source_bulkhead().in_flight(source_id) == 0


@pytest.mark.parametrize("oversized", ["input", "instructions"])
async def test_bridge_transcript_is_bounded(async_client, app_instance, monkeypatch, oversized):
    import app.modules.proxy.api as api

    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse(request, _turn_events(f"resp_{len(bodies)}", [MESSAGE]))

    monkeypatch.setattr(api, "request_body_limit_for_path", lambda path: 2048)
    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "short"})
            assert (await _receive_turn(ws))[-1]["type"] == "response.completed"
            continuation: dict[str, Any] = {
                "type": "response.create",
                "model": "source-ws-model",
                "previous_response_id": "resp_1",
                "input": "x" * 4096 if oversized == "input" else [],
            }
            if oversized == "instructions":
                # The input fits; the rest of the reconstructed resend does not.
                continuation["instructions"] = "y" * 4096
            await ws.send(continuation)
            event = await ws.receive()
    assert event["type"] == "error" and event["error"]["code"] == "invalid_request_error", event
    assert len(bodies) == 1


@pytest.mark.parametrize("over", [0, 1])
async def test_bridge_resend_limit_boundary(async_client, app_instance, monkeypatch, over):
    import app.modules.proxy.api as api

    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse(request, _turn_events(f"resp_{len(bodies)}", [MESSAGE]))

    instructions = "ỹ" * 300
    # The HTTP-equivalent resend Codex would send for the continuation below.
    resend = {
        "model": "source-ws-model",
        "instructions": instructions,
        "input": [{"role": "user", "content": "short"}, MESSAGE],
    }
    size = len(json.dumps(resend, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    monkeypatch.setattr(api, "request_body_limit_for_path", lambda path: size - over)
    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "short"})
            assert (await _receive_turn(ws))[-1]["type"] == "response.completed"
            await ws.send(
                {
                    "type": "response.create",
                    "model": "source-ws-model",
                    "previous_response_id": "resp_1",
                    "instructions": instructions,
                    "input": [],
                }
            )
            last = (await _receive_turn(ws))[-1]
    if over:
        assert last["type"] == "error" and last["error"]["code"] == "invalid_request_error", last
        assert len(bodies) == 1
    else:
        assert last["type"] == "response.completed", last
        assert len(bodies) == 2


def _prefix(response_id: str) -> list[dict[str, Any]]:
    """The lifecycle prefix ch-relay sends before an early moderation verdict (shape seen on 2026-10-23)."""
    return [
        {"type": "response.created", "sequence_number": 0, "response": _envelope(response_id, "in_progress", [])},
        {"type": "response.in_progress", "sequence_number": 1, "response": _envelope(response_id, "in_progress", [])},
        {
            "type": "response.metadata",
            "sequence_number": 2,
            "response_id": response_id,
            "metadata": {"openai_chatgpt_moderation_metadata": {"blocked": False, "flags": []}},
        },
    ]


EMPTY_MESSAGE: dict[str, Any] = {
    **MESSAGE,
    "id": "msg_empty",
    "content": [{"type": "output_text", "text": "", "annotations": []}],
}


def _empty_turn(response_id: str) -> list[dict[str, Any]]:
    """A source turn whose only output is reasoning and an empty assistant message."""
    in_progress = {**EMPTY_MESSAGE, "status": "in_progress", "content": []}
    part = {"type": "output_text", "text": ""}
    ids = {"item_id": "msg_empty", "output_index": 1, "content_index": 0}
    return [
        {"type": "response.created", "response": _envelope(response_id, "in_progress", [])},
        {"type": "response.output_item.added", "output_index": 0, "item": REASONING},
        {"type": "response.output_item.done", "output_index": 0, "item": REASONING},
        {"type": "response.output_item.added", "output_index": 1, "item": in_progress},
        {"type": "response.content_part.added", **ids, "part": part},
        {"type": "response.output_text.done", **ids, "text": ""},
        {"type": "response.content_part.done", **ids, "part": part},
        {"type": "response.output_item.done", "output_index": 1, "item": EMPTY_MESSAGE},
        {
            "type": "response.completed",
            "response": _envelope(response_id, "completed", [REASONING, EMPTY_MESSAGE], usage=True),
        },
    ]


async def _sse_then_reset(request: web.Request, events: list[dict[str, Any]]) -> web.StreamResponse:
    """Stream ``events`` and close the connection mid-body, as a relay reset does."""

    response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
    await response.prepare(request)
    for event in events:
        await response.write(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode())
    assert request.transport is not None
    request.transport.close()
    return response


def _overloaded(response_id: str) -> dict[str, Any]:
    failed = _envelope(response_id, "failed", [])
    failed["error"] = {"code": "server_is_overloaded", "message": "overloaded at https://private.example"}
    return {"type": "response.failed", "response": failed}


@pytest.mark.parametrize("failure", ["reset", "eof", "overloaded"])
async def test_bridge_pre_content_failure_is_replayed_invisibly(async_client, app_instance, failure):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        if len(bodies) == 1:
            if failure == "reset":
                return await _sse_then_reset(request, _prefix("resp_lost"))
            if failure == "eof":
                return await _sse(request, _prefix("resp_lost"))
            return await _sse(request, [*_prefix("resp_lost"), _overloaded("resp_lost")])
        return await _sse(request, _turn_events("resp_ok", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [USER_MESSAGE]})
            turn = await _receive_turn(ws)
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "next"})
            assert (await _receive_turn(ws))[-1]["type"] == "response.completed"
        rows, reservations = await _rows(source_id)
    assert [event["type"] for event in turn] == [
        "response.created",
        "response.output_item.added",
        "response.output_item.done",
        "response.completed",
    ]
    assert turn[0]["response"]["id"] == "resp_ok"
    assert len(bodies) == 3 and bodies[0] == bodies[1]
    first_code = "model_source_response_failed" if failure == "overloaded" else "model_source_stream_truncated"
    assert [(row.status, row.error_code) for row in rows] == [
        ("error", first_code),
        ("success", None),
        ("success", None),
    ]
    events = "created,in_progress,metadata,failed" if failure == "overloaded" else "created,in_progress,metadata"
    assert rows[0].failure_detail == f"source_bridge events={events} handed_off=none replay=eligible"
    assert rows[0].upstream_error_code == ("server_is_overloaded" if failure == "overloaded" else None)
    assert rows[1].failure_detail is None
    assert "private.example" not in json.dumps({column: str(value) for column, value in vars(rows[0]).items()})
    assert [reservation.status for reservation in reservations] == ["released", "finalized", "finalized"]
    assert get_source_bulkhead().in_flight(source_id) == 0


async def test_bridge_failure_after_content_is_not_replayed(async_client, app_instance):
    bodies: list[dict[str, Any]] = []
    streaming_message = {**MESSAGE, "status": "in_progress", "content": []}
    delta = {"type": "response.output_text.delta", "item_id": "msg_2", "output_index": 0, "delta": "par"}

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse_then_reset(
            request,
            [
                {"type": "response.created", "response": _envelope("resp_partial", "in_progress", [])},
                {"type": "response.output_item.added", "output_index": 0, "item": streaming_message},
                delta,
                delta,
                delta,
            ],
        )

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            turn = await _receive_turn(ws)
        rows, reservations = await _rows(source_id)
    assert [event["type"] for event in turn] == [
        "response.created",
        "response.output_item.added",
        "response.output_text.delta",
        "response.output_text.delta",
        "response.output_text.delta",
        "error",
    ]
    assert turn[-1]["error"]["code"] == "model_source_stream_truncated"
    assert len(bodies) == 1
    assert [(row.status, row.error_code, row.failure_detail) for row in rows] == [
        (
            "error",
            "model_source_stream_truncated",
            "source_bridge events=created,output_item,delta handed_off=content replay=none",
        )
    ]
    assert [reservation.status for reservation in reservations] == ["released"]


async def test_bridge_server_error_before_content_is_not_replayed(async_client, app_instance):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        failed = _envelope("resp_failed", "failed", [])
        failed["error"] = {"code": "server_error", "message": "boom"}
        return await _sse(request, [*_prefix("resp_failed"), {"type": "response.failed", "response": failed}])

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            turn = await _receive_turn(ws)
        rows, reservations = await _rows(source_id)
    assert [event["type"] for event in turn] == [
        "response.created",
        "response.in_progress",
        "response.metadata",
        "response.failed",
    ]
    assert turn[-1]["response"]["error"]["code"] == "model_source_response_failed"
    assert len(bodies) == 1
    assert [(row.error_code, row.upstream_error_code, row.failure_detail) for row in rows] == [
        (
            "model_source_response_failed",
            "server_error",
            "source_bridge events=created,in_progress,metadata,failed handed_off=content replay=none",
        )
    ]
    assert [reservation.status for reservation in reservations] == ["released"]


async def test_bridge_replacement_failure_is_not_replayed_again(async_client, app_instance):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse_then_reset(request, _prefix(f"resp_lost_{len(bodies)}"))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            turn = await _receive_turn(ws)
        rows, reservations = await _rows(source_id)
    assert [event["type"] for event in turn] == [
        "response.created",
        "response.in_progress",
        "response.metadata",
        "error",
    ]
    assert turn[0]["response"]["id"] == "resp_lost_2"
    assert turn[-1]["error"]["code"] == "model_source_stream_truncated"
    assert len(bodies) == 2
    assert [(row.error_code, row.failure_detail) for row in rows] == [
        (
            "model_source_stream_truncated",
            "source_bridge events=created,in_progress,metadata handed_off=none replay=eligible",
        ),
        (
            "model_source_stream_truncated",
            "source_bridge events=created,in_progress,metadata handed_off=prefix replay=none",
        ),
    ]
    assert [reservation.status for reservation in reservations] == ["released", "released"]
    assert get_source_bulkhead().in_flight(source_id) == 0


async def test_bridge_replay_without_admission_returns_the_original_failure(async_client, app_instance, monkeypatch):
    import app.modules.proxy.api as api

    bodies: list[dict[str, Any]] = []
    claims = 0
    original_claim = api.try_claim_source_admission

    def claim_once(source):
        nonlocal claims
        claims += 1
        return original_claim(source) if claims == 1 else None

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse_then_reset(request, _prefix("resp_lost"))

    monkeypatch.setattr(api, "try_claim_source_admission", claim_once)
    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            event = await ws.receive()
        rows, reservations = await _rows(source_id)
    assert event["type"] == "error" and event["status"] == 502, event
    assert event["error"]["code"] == "model_source_stream_truncated"
    assert claims == 2 and len(bodies) == 1
    assert [(row.status, row.error_code) for row in rows] == [("error", "model_source_stream_truncated")]
    assert [reservation.status for reservation in reservations] == ["released"]
    assert get_source_bulkhead().in_flight(source_id) == 0


def _failing_transport(app_instance, failing_type: str, frames: list[dict[str, Any]], closed: asyncio.Event):
    """ASGI wrapper whose downstream fails right after handing ``failing_type`` to the transport."""

    async def transport(scope, receive, send):
        async def intercepted(message):
            await send(message)
            if message["type"] == "websocket.send":
                frames.append(json.loads(message["text"]))
                if frames[-1]["type"] == failing_type:
                    raise OSError("downstream closed after handoff")

        try:
            await app_instance(scope, receive, intercepted)
        finally:
            closed.set()

    return transport


async def test_bridge_prefix_flush_does_not_deliver_an_observed_terminal(async_client, app_instance):
    frames: list[dict[str, Any]] = []
    closed = asyncio.Event()

    async def handler(request: web.Request) -> web.StreamResponse:
        await request.json()
        completed = {"type": "response.completed", "response": _envelope("resp_x", "completed", [], usage=True)}
        return await _sse(request, [_prefix("resp_x")[0], completed])

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        transport = _failing_transport(app_instance, "response.created", frames, closed)
        async with websocket_client(transport, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            assert (await ws.receive())["type"] == "response.created"
            await asyncio.wait_for(closed.wait(), 5)
        rows, reservations = await _rows(source_id)
    assert [frame["type"] for frame in frames] == ["response.created"]
    # The completed terminal was observed while the prefix flushed but never handed off.
    assert [row.status for row in rows] != ["success"]
    assert [reservation.status for reservation in reservations] == ["released"]


async def test_bridge_trace_counts_content_handed_off_before_a_send_failure(async_client, app_instance):
    frames: list[dict[str, Any]] = []
    closed = asyncio.Event()

    async def handler(request: web.Request) -> web.StreamResponse:
        await request.json()
        return await _sse(request, _turn_events("resp_x", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        transport = _failing_transport(app_instance, "response.output_item.added", frames, closed)
        async with websocket_client(transport, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            while (await ws.receive())["type"] != "response.output_item.added":
                pass
            await asyncio.wait_for(closed.wait(), 5)
        rows, _ = await _rows(source_id)
    assert [frame["type"] for frame in frames] == ["response.created", "response.output_item.added"]
    assert len(rows) == 1 and rows[0].status != "success"
    assert rows[0].failure_detail == "source_bridge events=created,output_item handed_off=content replay=none"


async def test_bridge_replay_requires_the_same_effective_body(async_client, app_instance):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        if len(bodies) == 1:
            # Source policy changes while the first attempt is in flight.
            overrides = {"source_request_overrides": {"instructions": "new instructions"}}
            async with SessionLocal() as session:
                await session.execute(
                    update(ModelSourceModel)
                    .where(ModelSourceModel.source_id == source_id)
                    .values(raw_metadata_json=json.dumps(overrides))
                )
                await session.commit()
            return await _sse_then_reset(request, _prefix("resp_lost"))
        return await _sse(request, _turn_events("resp_ok", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send(
                {"type": "response.create", "model": "source-ws-model", "input": "hi", "instructions": "original"}
            )
            event = await ws.receive()
        rows, reservations = await _rows(source_id)
    assert event["type"] == "error" and event["error"]["code"] == "model_source_stream_truncated", event
    assert [body["instructions"] for body in bodies] == ["original"]
    assert [(row.error_code, row.failure_detail) for row in rows] == [
        (
            "model_source_stream_truncated",
            "source_bridge events=created,in_progress,metadata handed_off=none replay=eligible",
        )
    ]
    assert [reservation.status for reservation in reservations] == ["released"]
    assert get_source_bulkhead().in_flight(source_id) == 0


async def test_bridge_outsized_prefix_is_relayed_and_not_replayed(async_client, app_instance, monkeypatch):
    from app.modules.proxy import source_websocket

    bodies: list[dict[str, Any]] = []
    monkeypatch.setattr(source_websocket, "SOURCE_STREAM_WITHHELD_CAP_BYTES", 400)

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse_then_reset(request, _prefix("resp_big"))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            turn = await _receive_turn(ws)
        rows, reservations = await _rows(source_id)
    assert [event["type"] for event in turn] == [
        "response.created",
        "response.in_progress",
        "response.metadata",
        "error",
    ]
    assert len(bodies) == 1
    assert [row.failure_detail for row in rows] == [
        "source_bridge events=created,in_progress,metadata handed_off=prefix replay=none"
    ]
    assert [reservation.status for reservation in reservations] == ["released"]


@pytest.mark.parametrize("case", ["text", "call", "empty_message_then_call", "whitespace_then_text"])
async def test_bridge_reasoning_is_held_until_visible_output(async_client, app_instance, case):
    bodies: list[dict[str, Any]] = []
    streaming = {**MESSAGE, "status": "in_progress", "content": []}
    delta = {"type": "response.output_text.delta", "item_id": "msg_2", "output_index": 1}
    source_events = {
        "text": _turn_events("resp_ok", [REASONING, MESSAGE]),
        "call": _turn_events("resp_ok", [REASONING, FUNCTION_CALL]),
        "empty_message_then_call": _turn_events("resp_ok", [REASONING, EMPTY_MESSAGE, FUNCTION_CALL]),
        "whitespace_then_text": [
            {"type": "response.created", "response": _envelope("resp_ok", "in_progress", [])},
            {"type": "response.output_item.added", "output_index": 0, "item": REASONING},
            {"type": "response.output_item.done", "output_index": 0, "item": REASONING},
            {"type": "response.output_item.added", "output_index": 1, "item": streaming},
            {**delta, "delta": "\n"},
            {**delta, "delta": "done"},
            {"type": "response.output_item.done", "output_index": 1, "item": MESSAGE},
            {
                "type": "response.completed",
                "response": _envelope("resp_ok", "completed", [REASONING, MESSAGE], usage=True),
            },
        ],
    }[case]

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        if len(bodies) == 1:
            return await _sse(request, source_events)
        return await _sse(request, _turn_events("resp_next", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [USER_MESSAGE]})
            turn = await _receive_turn(ws)
            if case == "empty_message_then_call":
                await ws.send(
                    {
                        "type": "response.create",
                        "model": "source-ws-model",
                        "previous_response_id": "resp_ok",
                        "input": [TOOL_OUTPUT],
                    }
                )
                assert (await _receive_turn(ws))[-1]["type"] == "response.completed"
        rows, _ = await _rows(source_id)
    assert [event["type"] for event in turn] == [event["type"] for event in source_events]
    assert len(bodies) == (2 if case == "empty_message_then_call" else 1)
    expected = [("success", None)] * len(bodies)
    assert [(row.status, row.error_code) for row in rows] == expected
    if case == "empty_message_then_call":
        # The request model already drops the empty ``annotations`` list from resent history.
        resent = {**EMPTY_MESSAGE, "content": [{"type": "output_text", "text": ""}]}
        assert bodies[1]["input"] == [USER_MESSAGE, REASONING, resent, FUNCTION_CALL, TOOL_OUTPUT]


async def test_bridge_reset_during_reasoning_is_replayed(async_client, app_instance):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        if len(bodies) == 1:
            return await _sse_then_reset(
                request,
                [
                    {"type": "response.created", "response": _envelope("resp_lost", "in_progress", [])},
                    {"type": "response.output_item.added", "output_index": 0, "item": REASONING},
                ],
            )
        return await _sse(request, _turn_events("resp_ok", [MESSAGE]))

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [USER_MESSAGE]})
            turn = await _receive_turn(ws)
        rows, reservations = await _rows(source_id)
    assert turn[0]["response"]["id"] == "resp_ok" and len(bodies) == 2 and bodies[0] == bodies[1]
    assert rows[0].failure_detail == "source_bridge events=created,output_item handed_off=none replay=eligible"
    assert [reservation.status for reservation in reservations] == ["released", "finalized"]


async def test_bridge_incomplete_after_reasoning_is_delivered(async_client, app_instance):
    bodies: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse(
            request,
            [
                {"type": "response.created", "response": _envelope("resp_inc", "in_progress", [])},
                {"type": "response.output_item.added", "output_index": 0, "item": REASONING},
                {"type": "response.output_item.done", "output_index": 0, "item": REASONING},
                {
                    "type": "response.incomplete",
                    "response": _envelope("resp_inc", "incomplete", [REASONING], usage=True),
                },
            ],
        )

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": [USER_MESSAGE]})
            turn = await _receive_turn(ws)
    assert [event["type"] for event in turn] == [
        "response.created",
        "response.output_item.added",
        "response.output_item.done",
        "response.incomplete",
    ]
    assert len(bodies) == 1


async def test_bridge_outsized_reasoning_is_relayed_and_not_replayed(async_client, app_instance, monkeypatch):
    from app.modules.proxy import source_websocket

    bodies: list[dict[str, Any]] = []
    monkeypatch.setattr(source_websocket, "SOURCE_STREAM_WITHHELD_CAP_BYTES", 400)
    big = {**REASONING, "encrypted_content": "x" * 1000}

    async def handler(request: web.Request) -> web.StreamResponse:
        bodies.append(await request.json())
        return await _sse_then_reset(
            request,
            [
                {"type": "response.created", "response": _envelope("resp_big", "in_progress", [])},
                {"type": "response.output_item.added", "output_index": 0, "item": big},
            ],
        )

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1), enabled=False)
        key = await create_key(async_client, source_id)
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({"type": "response.create", "model": "source-ws-model", "input": "hi"})
            turn = await _receive_turn(ws)
        rows, _ = await _rows(source_id)
    assert [event["type"] for event in turn] == ["response.created", "response.output_item.added", "error"]
    assert len(bodies) == 1
    assert rows[0].failure_detail == "source_bridge events=created,output_item handed_off=content replay=none"
