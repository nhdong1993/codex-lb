"""Per-model Codex sub-agent blocking on source-routed Responses traffic."""

from __future__ import annotations

import json

import pytest
from aiohttp import WSMsgType, web
from sqlalchemy import select

from app.db.models import ApiKeyUsageReservation
from app.db.session import SessionLocal
from tests.integration.model_source_helpers import _create_model_source, stub_source_upstreams
from tests.integration.test_model_source_websocket import complete, create_key, create_source, websocket_client

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

RESPONSES_PATHS = ["/v1/responses", "/v1/responses/", "/backend-api/codex/responses", "/backend-api/codex/responses/"]
BLOCKING_METADATA = json.dumps({"experimental_supported_tools": ["namespace"], "block_subagents": True})
SHELL_TOOL = {"type": "function", "name": "exec_command", "parameters": {"type": "object", "properties": {}}}
SUBAGENT_TOOL = {
    "type": "namespace",
    "name": "multi_agent_v1",
    "description": "Sub-agents",
    "tools": [{"type": "function", "name": "spawn_agent", "parameters": {"type": "object", "properties": {}}}],
}
MCP_TOOL = {
    "type": "namespace",
    "name": "mcp__demo",
    "description": "Demo MCP server",
    "tools": [{"type": "function", "name": "lookup", "parameters": {"type": "object", "properties": {}}}],
}
SPAWNED_CLIENT_METADATA = {"x-openai-subagent": "collab_spawn", "x-codex-parent-thread-id": "thread-parent"}
SPAWNED_TURN_METADATA = json.dumps({"thread_source": "subagent", "subagent_kind": "thread_spawn"})


@pytest.fixture
async def source_upstream():
    async with stub_source_upstreams() as start:
        yield start


def _recording_responses_handler(seen: list[dict[str, object]]):
    async def handler(request: web.Request) -> web.Response:
        seen.append(await request.json())
        body = (
            b'data: {"type":"response.created","response":{"id":"resp_sub","status":"in_progress","output":[]}}\n\n'
            b'data: {"type":"response.completed","response":{"id":"resp_sub","status":"completed","output":[],'
            b'"usage":{"input_tokens":2,"output_tokens":1,"total_tokens":3}}}\n\n'
        )
        return web.Response(body=body, headers={"Content-Type": "text/event-stream"})

    return handler


def _responses_body(model: str, **extra: object) -> dict[str, object]:
    return {"model": model, "instructions": "hi", "input": [], "stream": True, **extra}


@pytest.mark.parametrize("path", RESPONSES_PATHS)
async def test_blocking_model_strips_subagent_namespaces_and_keeps_mcp(async_client, source_upstream, path):
    seen: list[dict[str, object]] = []
    base_url = await source_upstream(_recording_responses_handler(seen))
    await _create_model_source(
        async_client,
        name="blocking",
        model="blocking-model",
        base_url=base_url,
        supports_responses=True,
        raw_metadata_json=BLOCKING_METADATA,
    )

    response = await async_client.post(
        path,
        json=_responses_body(
            "blocking-model",
            tools=[SHELL_TOOL, SUBAGENT_TOOL, MCP_TOOL],
            tool_choice={"type": "namespace", "name": "multi_agent_v1"},
            parallel_tool_calls=True,
        ),
    )

    assert response.status_code == 200, response.text
    assert seen[0]["tools"] == [SHELL_TOOL, MCP_TOOL]
    assert "tool_choice" not in seen[0]
    assert seen[0]["parallel_tool_calls"] is True


@pytest.mark.parametrize(
    "extra_body,headers",
    [
        ({"client_metadata": SPAWNED_CLIENT_METADATA}, {}),
        ({}, {"x-openai-subagent": "collab_spawn"}),
        ({"client_metadata": {"x-codex-turn-metadata": SPAWNED_TURN_METADATA}}, {}),
    ],
    ids=["client-metadata", "header", "turn-metadata"],
)
async def test_spawned_subagent_request_is_refused_before_reservation(
    async_client, source_upstream, extra_body, headers
):
    seen: list[dict[str, object]] = []
    base_url = await source_upstream(_recording_responses_handler(seen))
    source_id = await _create_model_source(
        async_client,
        name="blocking",
        model="blocking-model",
        base_url=base_url,
        supports_responses=True,
        raw_metadata_json=BLOCKING_METADATA,
    )
    key = await create_key(async_client, source_id)

    response = await async_client.post(
        "/backend-api/codex/responses",
        json=_responses_body("blocking-model", tools=[SHELL_TOOL], **extra_body),
        headers={"Authorization": f"Bearer {key['key']}", **headers},
    )

    assert response.status_code == 403, response.text
    error = response.json()["error"]
    assert error["code"] == "subagents_disabled"
    assert error["type"] == "invalid_request_error"
    assert seen == []
    async with SessionLocal() as session:
        assert not (await session.execute(select(ApiKeyUsageReservation))).scalars().all()


@pytest.mark.parametrize(
    "metadata,subagent_value",
    [(None, "collab_spawn"), (BLOCKING_METADATA, "compact")],
    ids=["unflagged-model", "other-auxiliary-thread"],
)
async def test_other_models_and_threads_are_forwarded(async_client, source_upstream, metadata, subagent_value):
    seen: list[dict[str, object]] = []
    base_url = await source_upstream(_recording_responses_handler(seen))
    await _create_model_source(
        async_client,
        name="source",
        model="source-model",
        base_url=base_url,
        supports_responses=True,
        raw_metadata_json=metadata,
    )

    response = await async_client.post(
        "/backend-api/codex/responses",
        json=_responses_body("source-model", client_metadata={"x-openai-subagent": subagent_value}),
        headers={"x-openai-subagent": subagent_value},
    )

    assert response.status_code == 200, response.text
    assert len(seen) == 1


async def test_spawned_subagent_request_uses_a_pool_member_that_allows_subagents(async_client, source_upstream):
    blocked_seen: list[dict[str, object]] = []
    allowed_seen: list[dict[str, object]] = []
    await _create_model_source(
        async_client,
        name="pool-blocking",
        model="pooled-model",
        base_url=await source_upstream(_recording_responses_handler(blocked_seen)),
        supports_responses=True,
        raw_metadata_json=BLOCKING_METADATA,
    )
    await _create_model_source(
        async_client,
        name="pool-allowing",
        model="pooled-model",
        base_url=await source_upstream(_recording_responses_handler(allowed_seen)),
        supports_responses=True,
    )

    for _ in range(3):
        response = await async_client.post(
            "/backend-api/codex/responses",
            json=_responses_body("pooled-model", client_metadata=SPAWNED_CLIENT_METADATA),
        )
        assert response.status_code == 200, response.text

    assert blocked_seen == []
    assert len(allowed_seen) == 3


async def test_aliases_of_one_upstream_keep_separate_subagent_policies(async_client, source_upstream):
    seen: list[dict[str, object]] = []
    base_url = await source_upstream(_recording_responses_handler(seen))
    response = await async_client.post(
        "/api/model-sources/",
        json={
            "name": "aliases",
            "baseUrl": base_url,
            "supportsResponses": True,
            "models": [
                {"model": "open/shared", "rawMetadataJson": json.dumps({"upstream_model": "shared-upstream"})},
                {
                    "model": "noagent/shared",
                    "rawMetadataJson": json.dumps({"upstream_model": "shared-upstream", "block_subagents": True}),
                },
            ],
        },
    )
    assert response.status_code == 200, response.text

    allowed = await async_client.post(
        "/v1/responses", json=_responses_body("open/shared", client_metadata=SPAWNED_CLIENT_METADATA)
    )
    blocked = await async_client.post(
        "/v1/responses", json=_responses_body("noagent/shared", client_metadata=SPAWNED_CLIENT_METADATA)
    )

    assert allowed.status_code == 200, allowed.text
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["error"]["code"] == "subagents_disabled"
    assert [request["model"] for request in seen] == ["shared-upstream"]


async def _create_mixed_policy_pool(async_client, source_upstream, blocking_handler, allowing_handler) -> None:
    await _create_model_source(
        async_client,
        name="pool-blocking",
        model="pooled-model",
        base_url=await source_upstream(blocking_handler),
        supports_responses=True,
        raw_metadata_json=BLOCKING_METADATA,
    )
    await _create_model_source(
        async_client,
        name="pool-allowing",
        model="pooled-model",
        base_url=await source_upstream(allowing_handler),
        supports_responses=True,
    )


async def test_spawned_subagent_in_mixed_pool_keeps_unknown_anchor_fail_closed(async_client, source_upstream):
    blocked_seen: list[dict[str, object]] = []
    allowed_seen: list[dict[str, object]] = []
    await _create_mixed_policy_pool(
        async_client,
        source_upstream,
        _recording_responses_handler(blocked_seen),
        _recording_responses_handler(allowed_seen),
    )

    response = await async_client.post(
        "/v1/responses",
        json=_responses_body(
            "pooled-model", previous_response_id="resp_unknown_external", client_metadata=SPAWNED_CLIENT_METADATA
        ),
    )

    assert response.status_code == 409, response.text
    assert blocked_seen == []
    assert allowed_seen == []


async def test_spawned_subagent_in_mixed_pool_respects_cooldown(async_client, source_upstream):
    calls = {"blocking": 0, "allowing": 0}

    def rate_limited(name: str):
        async def handler(request: web.Request) -> web.Response:
            calls[name] += 1
            return web.json_response({"error": {"message": "slow down", "type": "rate_limit_error"}}, status=429)

        return handler

    await _create_mixed_policy_pool(async_client, source_upstream, rate_limited("blocking"), rate_limited("allowing"))
    parent = await async_client.post("/v1/responses", json=_responses_body("pooled-model"))
    assert parent.status_code >= 400, parent.text
    assert calls["allowing"] == 1

    spawned = await async_client.post(
        "/v1/responses", json=_responses_body("pooled-model", client_metadata=SPAWNED_CLIENT_METADATA)
    )

    assert spawned.status_code == 503, spawned.text
    assert spawned.json()["error"]["code"] == "model_source_busy"
    assert calls["allowing"] == 1


@pytest.mark.parametrize("signal", ["frame-metadata", "handshake-header"])
async def test_spawned_subagent_websocket_turn_is_refused(async_client, app_instance, signal):
    frames: list[dict[str, object]] = []

    async def handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            if message.type == WSMsgType.TEXT:
                frames.append(json.loads(message.data))
                await complete(ws)
        return ws

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(handler), metadata=BLOCKING_METADATA)
        key = await create_key(async_client, source_id)
        extra_headers = [(b"x-openai-subagent", b"collab_spawn")] if signal == "handshake-header" else []
        frame: dict[str, object] = {"type": "response.create", "model": "source-ws-model", "input": "hi"}
        if signal == "frame-metadata":
            frame["client_metadata"] = SPAWNED_CLIENT_METADATA
        async with websocket_client(app_instance, "/v1/responses", key["key"], extra_headers=extra_headers) as ws:
            await ws.send(frame)
            event = await ws.receive()

    assert event["type"] == "error"
    assert event["status"] == 403
    assert event["error"]["code"] == "subagents_disabled"
    assert frames == []
    async with SessionLocal() as session:
        assert not (await session.execute(select(ApiKeyUsageReservation))).scalars().all()


async def test_codex_catalog_hides_the_block_flag(async_client):
    await _create_model_source(
        async_client,
        name="blocking",
        model="blocking-model",
        base_url="http://127.0.0.1:9/v1",
        supports_responses=True,
        raw_metadata_json=BLOCKING_METADATA,
    )

    for path in ("/backend-api/codex/models", "/v1/models"):
        response = await async_client.get(path)
        assert response.status_code == 200, response.text
        assert "blocking-model" in response.text
        assert "block_subagents" not in response.text
