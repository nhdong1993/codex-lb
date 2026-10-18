"""Conversations continue on the same source after its revision changes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pytest
from aiohttp import WSMsgType, web
from sqlalchemy import select

from app.core.utils.time import utcnow
from app.db.models import ModelSourceOwnershipHistory
from app.db.session import SessionLocal
from app.modules.model_sources.ownership_repository import SourceOwnershipRepository
from app.modules.proxy.source_ownership import OwnershipScope
from tests.integration import test_model_source_pool as pool_fixtures
from tests.integration.model_source_helpers import stub_source_upstreams
from tests.integration.test_model_source_pool import MODEL, body
from tests.integration.test_model_source_websocket import create_key, create_source, websocket_client
from tests.integration.test_source_reference_scope_gaps import _set_model

make_pool = pool_fixtures.make_pool
pool_clock = pool_fixtures.pool_clock
pytestmark = pytest.mark.integration
CANONICAL_ROUTES = ["/v1/responses", "/backend-api/codex/responses"]


def user(text: str) -> dict[str, Any]:
    return {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}


def reasoning(n: int) -> dict[str, Any]:
    return {"type": "reasoning", "id": f"rs_{n}", "summary": [], "encrypted_content": f"cipher_{n}"}


def call(n: int, **extra: Any) -> dict[str, Any]:
    return {
        "type": "function_call",
        "id": f"fc_{n}",
        "call_id": f"call_{n}",
        "name": "exec",
        "arguments": "{}",
        **extra,
    }


def call_output(n: int) -> dict[str, Any]:
    return {"type": "function_call_output", "call_id": f"call_{n}", "output": "done"}


def assistant(n: int) -> dict[str, Any]:
    return {
        "type": "message",
        "id": f"msg_{n}",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": f"answer {n}"}],
    }


def without_id(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key not in {"id", "namespace"}}


@dataclass
class Upstream:
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    outputs: list[list[dict[str, Any]]] = field(default_factory=list)
    status: int = 200

    async def handler(self, request: web.Request) -> web.StreamResponse:
        token = request.headers["Authorization"].removeprefix("Bearer token-")
        sent = await request.json()
        self.calls.append((token, sent))
        if self.status != 200:
            return web.json_response({"error": {"message": "busy", "type": "server_error"}}, status=self.status)
        result = {
            "id": f"resp_stale_{len(self.calls)}",
            "object": "response",
            "status": "completed",
            "model": sent["model"],
            "output": self.outputs.pop(0) if self.outputs else [],
            "usage": {"input_tokens": 3, "output_tokens": 1, "total_tokens": 4},
        }
        if sent.get("stream"):
            return web.Response(
                text="data: " + json.dumps({"type": "response.completed", "response": result}) + "\n\n",
                content_type="text/event-stream",
            )
        return web.json_response(result)


async def _source(make_pool: Any, outputs: list[list[dict[str, Any]]]) -> tuple[Any, Upstream]:
    upstream = Upstream(outputs=outputs)
    pool = await make_pool(1, upstream.handler)
    return pool, upstream


async def _first_turn(async_client: Any, pool: Any, route: str) -> dict[str, Any]:
    first = await async_client.post(route, headers=pool.headers, json=body(input=[user("u0")]))
    assert first.status_code == 200, first.text
    return first.json()


async def _move_mapping(async_client: Any, pool: Any, **metadata: Any) -> None:
    await _set_model(async_client, pool.ids[0], MODEL, "upstream-moved", **metadata)


async def _revisions(pool: Any, kind: str, value: str) -> set[str]:
    key = OwnershipScope(pool.key_id, MODEL).key(kind, value)
    async with SessionLocal() as session:
        rows = await session.scalars(
            select(ModelSourceOwnershipHistory).where(ModelSourceOwnershipHistory.reference_key == key)
        )
        return {row.source_revision for row in rows}


@pytest.mark.parametrize("route", CANONICAL_ROUTES)
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("change", ["upstream-model", "token"])
@pytest.mark.parametrize("namespace", [None, "functions"])
async def test_tool_continuation_after_reconfiguration_drops_stale_state(
    async_client: Any, make_pool: Any, route: str, stream: bool, change: str, namespace: str | None
) -> None:
    extra = {} if namespace is None else {"namespace": namespace}
    pool, upstream = await _source(make_pool, [[reasoning(1), call(1, **extra)]])
    first = await _first_turn(async_client, pool, route)
    if change == "upstream-model":
        await _move_mapping(async_client, pool)
    else:
        rotated = await async_client.patch(f"/api/model-sources/{pool.ids[0]}", json={"apiKey": "token-rotated"})
        assert rotated.status_code == 200, rotated.text
    # Codex resends the whole transcript; the turn ends with the tool result.
    transcript = [user("u0"), *first["output"], call_output(1)]

    second = await async_client.post(route, headers=pool.headers, json=body(stream=stream, input=transcript))

    assert second.status_code == 200, second.text
    token, sent = upstream.calls[-1]
    assert token == ("pool-0" if change == "upstream-model" else "rotated")
    assert sent["input"] == [user("u0"), without_id(call(1)), call_output(1)]
    # The stale references were never sent to, or recorded under, the new revision.
    assert len(await _revisions(pool, "item", "rs_1")) == 1
    assert len(await _revisions(pool, "item", "fc_1")) == 1


async def test_items_from_the_current_revision_are_kept(async_client: Any, make_pool: Any) -> None:
    pool, upstream = await _source(make_pool, [[reasoning(1), assistant(1)], [reasoning(2), call(2)]])
    first = await _first_turn(async_client, pool, "/v1/responses")
    await _move_mapping(async_client, pool)
    turn = [user("u0"), *first["output"], user("u1")]
    second = await async_client.post("/v1/responses", headers=pool.headers, json=body(input=turn))
    assert second.status_code == 200, second.text
    assert upstream.calls[-1][1]["input"] == [user("u0"), without_id(assistant(1)), user("u1")]

    current = second.json()["output"]
    third = await async_client.post(
        "/v1/responses", headers=pool.headers, json=body(input=[*turn, *current, call_output(2)])
    )

    assert third.status_code == 200, third.text
    assert upstream.calls[-1][1]["input"] == [
        user("u0"),
        without_id(assistant(1)),
        user("u1"),
        *current,
        call_output(2),
    ]
    assert current == [reasoning(2), call(2)]


async def _seed(pool: Any, kind: str, value: str, *, source_id: str, revision: str) -> None:
    async with SessionLocal() as session:
        await SourceOwnershipRepository(session).claim(
            [OwnershipScope(pool.key_id, MODEL).key(kind, value)],
            source_id=source_id,
            source_revision=revision,
            expires_at=utcnow() + timedelta(days=30),
        )
        await session.commit()


@pytest.mark.parametrize("route", CANONICAL_ROUTES)
@pytest.mark.parametrize(
    "guard",
    [
        "previous-response",
        "override-clears-anchor",
        "compaction",
        "item-reference",
        "reasoning-only",
        "foreign-owner",
        "unresolved-call",
        "override-restores-stale-id",
    ],
)
async def test_state_projection_cannot_remove_still_fails_closed(
    async_client: Any, make_pool: Any, route: str, guard: str
) -> None:
    pool, upstream = await _source(make_pool, [[reasoning(1), call(1), assistant(1)]])
    first = await _first_turn(async_client, pool, route)
    (old_revision,) = await _revisions(pool, "item", "rs_1")
    if guard == "override-clears-anchor":
        await _move_mapping(async_client, pool, source_request_overrides={"previous_response_id": None})
    elif guard == "override-restores-stale-id":
        await _move_mapping(async_client, pool, source_request_overrides={"input": [call(1), call_output(1)]})
    else:
        await _move_mapping(async_client, pool)
    transcript = [user("u0"), *first["output"], call_output(1), user("u1")]
    payload = body(input=transcript)
    if guard in {"previous-response", "override-clears-anchor"}:
        payload["previous_response_id"] = first["id"]
    elif guard == "compaction":
        await _seed(pool, "encrypted", "summary_1", source_id=pool.ids[0], revision=old_revision)
        payload["input"] = [user("u0"), reasoning(1), {"type": "compaction", "encrypted_content": "summary_1"}]
    elif guard == "item-reference":
        payload["input"] = [user("u0"), reasoning(1), {"type": "item_reference", "id": "msg_1"}, user("u1")]
    elif guard == "reasoning-only":
        payload["input"] = [reasoning(1)]
    elif guard == "foreign-owner":
        await _seed(pool, "item", "rs_foreign", source_id="src_other", revision="other-revision")
        payload["input"] = [*transcript, {**reasoning(9), "id": "rs_foreign"}, user("u2")]
    elif guard == "unresolved-call":
        payload["input"] = [user("u0"), call_output(1), user("u1")]
    before = len(upstream.calls)

    denied = await async_client.post(route, headers=pool.headers, json=payload)

    assert denied.status_code == 409, denied.text
    assert denied.json()["error"]["code"] in {"model_source_owner_unavailable", "previous_response_owner_unavailable"}
    assert len(upstream.calls) == before


async def test_override_removing_a_current_reference_keeps_the_dispatch_guard(
    async_client: Any, make_pool: Any
) -> None:
    pool, upstream = await _source(make_pool, [[reasoning(1), assistant(1)]])
    first = await _first_turn(async_client, pool, "/v1/responses")
    (old_revision,) = await _revisions(pool, "item", "rs_1")
    await _move_mapping(async_client, pool)
    owned = await async_client.post(
        "/v1/responses", headers=pool.headers, json=body(input=[user("x")], prompt={"id": "pmpt_current"})
    )
    assert owned.status_code == 200, owned.text
    (current_revision,) = await _revisions(pool, "prompt", "pmpt_current")
    assert current_revision != old_revision
    await _move_mapping(async_client, pool, source_request_overrides={"prompt": None})

    response = await async_client.post(
        "/v1/responses",
        headers=pool.headers,
        json=body(input=[user("u0"), *first["output"], user("u1")], prompt={"id": "pmpt_current"}),
    )

    assert response.status_code == 200, response.text
    sent = upstream.calls[-1][1]
    assert sent["prompt"] is None
    assert sent["input"] == [user("u0"), without_id(assistant(1)), user("u1")]
    for kind, value in [("item", "rs_1"), ("encrypted", "cipher_1"), ("item", "msg_1")]:
        assert await _revisions(pool, kind, value) == {old_revision}
    assert await _revisions(pool, "prompt", "pmpt_current") == {current_revision}


async def test_pool_projection_stays_on_the_owner_without_failover(async_client: Any, make_pool: Any) -> None:
    upstream = Upstream(outputs=[[reasoning(1), call(1)]])
    pool = await make_pool(2, upstream.handler)
    assigned = await async_client.patch(f"/api/api-keys/{pool.key_id}", json={"assignedSourceIds": pool.ids[:1]})
    assert assigned.status_code == 200, assigned.text
    first = await _first_turn(async_client, pool, "/v1/responses")
    assigned = await async_client.patch(f"/api/api-keys/{pool.key_id}", json={"assignedSourceIds": pool.ids})
    assert assigned.status_code == 200, assigned.text
    await _set_model(async_client, pool.ids[0], MODEL, "upstream-moved")
    transcript = [user("u0"), *first["output"], call_output(1)]

    projected = await async_client.post("/v1/responses", headers=pool.headers, json=body(input=transcript))
    assert projected.status_code == 200, projected.text
    assert upstream.calls[-1][0] == "pool-0"
    assert upstream.calls[-1][1]["input"] == [user("u0"), without_id(call(1)), call_output(1)]

    before = len(upstream.calls)
    upstream.status = 503
    failed = await async_client.post("/v1/responses", headers=pool.headers, json=body(input=transcript))
    assert failed.status_code != 200, failed.text
    assert [token for token, _ in upstream.calls[before:]] == ["pool-0"]


async def test_websocket_reconnect_projects_while_the_bound_socket_must_reconnect(async_client, app_instance):
    received: list[dict[str, Any]] = []
    output = [reasoning(1), call(1)]

    async def handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            if message.type != WSMsgType.TEXT:
                continue
            received.append(json.loads(message.data))
            response = {"id": f"resp_ws_{len(received)}", "model": "source-ws-model", "status": "completed"}
            response["output"] = output if len(received) == 1 else []
            response["usage"] = {"input_tokens": 3, "output_tokens": 1, "total_tokens": 4}
            await ws.send_json({"type": "response.created", "response": {**response, "status": "in_progress"}})
            await ws.send_json({"type": "response.completed", "response": response})
        return ws

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler, shutdown_timeout=1))
        key = await create_key(async_client, source_id)
        create = {"type": "response.create", "model": "source-ws-model", "input": [user("u0")]}
        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send(create)
            assert (await ws.receive())["type"] == "response.created"
            assert (await ws.receive())["type"] == "response.completed"
            moved = await async_client.patch(
                f"/api/model-sources/{source_id}",
                json={
                    "models": [
                        {
                            "model": "source-ws-model",
                            "supportsStreaming": True,
                            "supportsTools": True,
                            "rawMetadataJson": json.dumps({"upstream_model": "upstream-moved"}),
                        }
                    ]
                },
            )
            assert moved.status_code == 200, moved.text
            transcript = [user("u0"), *output, call_output(1)]
            await ws.send({**create, "input": transcript})
            assert (await ws.receive())["error"]["code"] == "websocket_reconnect_required"
        assert len(received) == 1

        async with websocket_client(app_instance, "/v1/responses", key["key"]) as ws:
            await ws.send({**create, "input": transcript})
            assert (await ws.receive())["type"] == "response.created"
            assert (await ws.receive())["type"] == "response.completed"
        assert len(received) == 2
        assert received[1]["model"] == "upstream-moved"
        assert received[1]["input"] == [user("u0"), without_id(call(1)), call_output(1)]
