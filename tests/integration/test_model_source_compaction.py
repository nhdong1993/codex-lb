from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from aiohttp import web
from sqlalchemy import select

from app.core.utils.sse import format_sse_event
from app.db.models import ApiKeyUsageReservation, RequestLog
from app.db.session import SessionLocal
from app.modules.api_keys.service import ApiKeysService
from app.modules.proxy import source_pool
from app.modules.proxy.source_admission import get_source_bulkhead
from tests.integration.model_source_helpers import (
    _AsgiStream,
    _create_model_source,
    _enable_api_key_auth,
    stub_source_upstreams,
)

pytestmark = pytest.mark.integration

MODEL = "source/compact-model"
COMPACT_PATHS = ["/v1/responses/compact", "/backend-api/codex/responses/compact"]
RESPONSE_PATHS = ["/v1/responses", "/backend-api/codex/responses"]
USAGE = {
    "input_tokens": 21,
    "output_tokens": 8,
    "total_tokens": 29,
    "input_tokens_details": {"cached_tokens": 10},
    "output_tokens_details": {"reasoning_tokens": 3},
}


@dataclass
class CompactProvider:
    ids: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    mode: str = "success"
    usage_location: str = "terminal_response"
    earlier_usage_override: dict[str, Any] | None = None
    terminal_usage_override: dict[str, Any] | None = None
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    abort_requested: asyncio.Event = field(default_factory=asyncio.Event)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        assert request.path == "/v1/responses"
        body = await request.json()
        token = request.headers["Authorization"]
        self.calls.append((token, body))
        self.entered.set()
        suffix = "_second" if token.endswith("compact-1") else ""
        response_id = "resp_compact" + suffix
        response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        created_response: dict[str, Any] = {"id": response_id}
        if self.usage_location.startswith("earlier"):
            created_response["usage"] = USAGE if self.earlier_usage_override is None else self.earlier_usage_override
        await response.write(format_sse_event({"type": "response.created", "response": created_response}).encode())
        if self.mode == "broken_connection":
            await self.abort_requested.wait()
            assert request.transport is not None
            request.transport.abort()
            return response
        if self.mode == "stall":
            try:
                await asyncio.Event().wait()
            finally:
                self.closed.set()
        if self.mode == "truncated":
            return response
        if self.mode.startswith("malformed_error"):
            event: dict[str, Any] = (
                {"type": "error", "code": 123, "message": "Provider failed"}
                if self.mode == "malformed_error_root"
                else {"type": "response.failed", "response": {"error": {"message": ["bad"]}}}
            )
            await response.write(format_sse_event(event).encode())
            return response
        if self.mode == "failed":
            await response.write(
                format_sse_event(
                    {
                        "type": "response.failed",
                        "response": {
                            "id": response_id,
                            "error": {"code": "invalid_request_error", "message": "Cannot compact"},
                        },
                    }
                ).encode()
            )
            return response
        item = {
            "id": "cmp_source" + suffix,
            "type": "compaction",
            "status": "completed",
            "encrypted_content": "cipher-source" + suffix,
        }
        if self.mode == "large":
            item["encrypted_content"] = "cipher-source" + "x" * 1_100_000
        output = [item] if self.mode != "missing_item" else []
        if self.mode == "item_done":
            await response.write(format_sse_event({"type": "response.output_item.done", "item": item}).encode())
            output = []
        if self.mode == "summary":
            item["type"] = "compaction_summary"
        if self.mode == "invalid_item_id":
            item["id"] = "not-a-compact-id"
        completed_response: dict[str, Any] = {
            "id": 123 if self.mode == "invalid_envelope" else response_id,
            "object": "response",
            "model": "upstream-model",
            "status": "completed",
            "output": output,
            "usage": USAGE,
        }
        terminal: dict[str, Any] = {
            "type": "response.completed",
            "response": completed_response,
        }
        if self.usage_location in ("terminal_root", "earlier_response", "none") or "root" in self.usage_location:
            completed_response.pop("usage")
        if self.usage_location == "terminal_root":
            terminal["usage"] = USAGE
        if self.usage_location == "earlier_then_root":
            terminal["usage"] = {**USAGE, "input_tokens": 30, "total_tokens": 38}
        if self.usage_location == "earlier_root_null":
            terminal["usage"] = None
        if self.usage_location == "earlier_root_negative":
            terminal["usage"] = {**USAGE, "input_tokens": -1}
        if self.usage_location == "earlier_root_missing_output":
            terminal["usage"] = {"input_tokens": 30}
        if self.usage_location == "earlier_root_invalid":
            terminal["usage"] = {**USAGE, "input_tokens": "invalid"}
        if self.usage_location == "earlier_null":
            completed_response["usage"] = None
        if self.usage_location == "earlier_then_terminal":
            completed_response["usage"] = {**USAGE, "input_tokens": 30, "total_tokens": 38}
        if self.usage_location == "earlier_then_invalid":
            completed_response["usage"] = {**USAGE, "input_tokens": "invalid"}
        if self.usage_location == "earlier_then_negative":
            completed_response["usage"] = {**USAGE, "input_tokens": -1}
        if self.terminal_usage_override is not None:
            if "root" in self.usage_location:
                terminal["usage"] = self.terminal_usage_override
            else:
                completed_response["usage"] = self.terminal_usage_override
        await response.write(format_sse_event(terminal).encode())
        return response


@pytest.fixture
async def provider(async_client, monkeypatch):
    await _enable_api_key_auth(async_client)
    provider = CompactProvider()
    monkeypatch.setattr(source_pool, "_SOURCE_POOL", source_pool.SourcePool())
    monkeypatch.setattr(source_pool.random, "choice", lambda values: values[0])
    async with stub_source_upstreams() as start:
        url = await start(provider.handle, handler_cancellation=True, shutdown_timeout=0.2)
        for i in range(2):
            provider.ids.append(
                await _create_model_source(
                    async_client,
                    name=f"compact-{i}",
                    model=MODEL,
                    base_url=url,
                    supports_responses=True,
                    raw_metadata_json=json.dumps({"upstream_model": "upstream-model"}),
                )
            )
        key = await async_client.post(
            "/api/api-keys/",
            json={
                "name": "compact-key",
                "assignedSourceIds": provider.ids,
                "allowedModels": [MODEL],
                "limits": [{"limitType": "total_tokens", "limitWindow": "weekly", "maxValue": 1000000}],
            },
        )
        assert key.status_code == 200
        provider.headers = {"Authorization": "Bearer " + key.json()["key"]}
        yield provider


def compact_body(*, trigger: bool = False) -> dict[str, Any]:
    items = [{"role": "user", "content": "Retain this history"}]
    if trigger:
        items.append({"type": "compaction_trigger"})
    return {"model": MODEL, "instructions": "Compress the history", "input": items, "stream": True}


async def reservations() -> list[ApiKeyUsageReservation]:
    async with SessionLocal() as session:
        return list((await session.scalars(select(ApiKeyUsageReservation))).all())


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize("disabled", [False, True])
async def test_compact_selects_streaming_model_fallback(async_client, monkeypatch, path, disabled):
    await _enable_api_key_auth(async_client)
    upstream = CompactProvider()
    monkeypatch.setattr(source_pool, "_SOURCE_POOL", source_pool.SourcePool())
    async with stub_source_upstreams() as start:
        url = await start(upstream.handle)
        ids = [
            await _create_model_source(
                async_client,
                name="nonstream-alias",
                model="gpt-5-high",
                base_url=url,
                supports_responses=True,
                supports_streaming=False,
            ),
            await _create_model_source(
                async_client, name="stream-fallback", model="gpt-5", base_url=url, supports_responses=True
            ),
        ]
        if disabled:
            changed = await async_client.patch(f"/api/model-sources/{ids[1]}", json={"isEnabled": False})
            assert changed.status_code == 200
        key = await async_client.post(
            "/api/api-keys/",
            json={
                "name": "streaming-compact",
                "assignedSourceIds": ids,
                "allowedModels": ["gpt-5-high", "gpt-5"],
                "limits": [{"limitType": "total_tokens", "limitWindow": "weekly", "maxValue": 1000000}],
            },
        )
        assert key.status_code == 200
        headers = {"Authorization": "Bearer " + key.json()["key"]}
        body = {**compact_body(), "model": "gpt-5-high"}
        response = await async_client.post(path, headers=headers, json=body)
        trigger = await async_client.post(
            path.removesuffix("/compact"),
            headers=headers,
            json={**compact_body(trigger=True), "model": "gpt-5-high"},
        )
        if disabled:
            assert response.status_code == trigger.status_code == 503
            assert response.json()["error"]["code"] == "model_source_disabled"
            assert "'gpt-5'" in response.json()["error"]["message"]
            assert not upstream.calls and not await reservations()
        else:
            assert response.status_code == trigger.status_code == 200, response.text
            assert response.json()["model"] == "gpt-5"
            assert len(upstream.calls) == 2
            for token, forwarded in upstream.calls:
                assert token == "Bearer token-stream-fallback"
                assert forwarded["model"] == "gpt-5" and forwarded["stream"] is True
            assert [row.status for row in await reservations()] == ["finalized"] * 2
        assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in ids)


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize("disabled", [False, True])
@pytest.mark.parametrize("subscription_owned", [False, True])
async def test_compact_nonstreaming_membership_blocks_fallback(
    async_client, monkeypatch, path, disabled, subscription_owned
):
    from unittest.mock import AsyncMock

    from app.core.openai.models import CompactResponsePayload
    from app.modules.proxy.service import ProxyService

    await _enable_api_key_auth(async_client)
    source_id = await _create_model_source(
        async_client,
        name="only-nonstream",
        model=MODEL,
        base_url="http://127.0.0.1:1/v1",
        supports_responses=True,
        supports_streaming=False,
    )
    if disabled:
        changed = await async_client.patch(f"/api/model-sources/{source_id}", json={"isEnabled": False})
        assert changed.status_code == 200
    key = await async_client.post(
        "/api/api-keys/",
        json={
            "name": "nonstream-compact",
            "assignedSourceIds": [source_id],
            "allowedModels": [MODEL],
            "limits": [{"limitType": "total_tokens", "limitWindow": "weekly", "maxValue": 1000000}],
        },
    )
    assert key.status_code == 200
    subscription = AsyncMock(
        return_value=CompactResponsePayload.model_validate(
            {"object": "response.compaction", "output": [{"type": "compaction", "encrypted_content": "account"}]}
        )
    )
    monkeypatch.setattr(ProxyService, "compact_responses", subscription)
    body = compact_body()
    if subscription_owned:
        body["previous_response_id"] = "resp_subscription"
        monkeypatch.setattr(
            ProxyService, "_resolve_websocket_previous_response_owner", AsyncMock(return_value="account")
        )
    response = await async_client.post(path, headers={"Authorization": "Bearer " + key.json()["key"]}, json=body)
    if subscription_owned:
        assert response.status_code == 200, response.text
        subscription.assert_awaited_once()
    else:
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == ("model_source_disabled" if disabled else "model_source_busy")
        subscription.assert_not_called()
        assert not await reservations()
    assert get_source_bulkhead().in_flight(source_id) == 0


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize("mode", ["success", "large"])
@pytest.mark.parametrize(
    "location",
    [
        "terminal_root",
        "earlier_response",
        "earlier_null",
        "earlier_then_terminal",
        "earlier_then_root",
        "earlier_root_null",
    ],
)
async def test_compact_preserves_observed_usage(async_client, provider, path, mode, location):
    provider.mode = mode
    provider.usage_location = location
    response = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert response.status_code == 200, response.text
    expected = (
        {**USAGE, "input_tokens": 30, "total_tokens": 38}
        if location in ("earlier_then_terminal", "earlier_then_root")
        else USAGE
    )
    assert response.json()["usage"] == expected
    rows = await reservations()
    assert len(rows) == 1 and rows[0].status == "finalized"
    assert (rows[0].input_tokens, rows[0].output_tokens, rows[0].cached_input_tokens) == (
        expected["input_tokens"],
        8,
        10,
    )
    async with SessionLocal() as session:
        log = (await session.scalars(select(RequestLog))).one()
        assert log.status == "success" and log.request_kind == "compaction"
        assert (log.input_tokens, log.output_tokens, log.cached_input_tokens, log.reasoning_tokens) == (
            expected["input_tokens"],
            8,
            10,
            3,
        )
    assert len(provider.calls) == 1
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize(
    "location",
    [
        "earlier_then_invalid",
        "earlier_then_negative",
        "earlier_root_negative",
        "earlier_root_missing_output",
        "earlier_root_invalid",
        "none",
    ],
)
async def test_compact_does_not_mask_invalid_or_missing_usage(async_client, provider, path, location):
    provider.usage_location = location
    response = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "usage_unavailable"
    assert "cipher-source" not in response.text
    assert len(provider.calls) == 1
    assert [row.status for row in await reservations()] == ["released"]
    async with SessionLocal() as session:
        log = (await session.scalars(select(RequestLog))).one()
        assert log.status == "error" and log.error_code == "usage_unavailable"
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize("location", ["earlier_then_terminal", "earlier_then_root"])
@pytest.mark.parametrize(
    "invalid_counters",
    [
        {"total_tokens": -1},
        {"input_tokens_details": {"cached_tokens": -1}},
        {"output_tokens_details": {"reasoning_tokens": -1}},
    ],
)
async def test_compact_rejects_negative_terminal_usage_details(
    async_client, provider, path, location, invalid_counters
):
    provider.usage_location = location
    provider.terminal_usage_override = {**USAGE, **invalid_counters}
    response = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "usage_unavailable"
    assert "cipher-source" not in response.text
    assert len(provider.calls) == 1
    assert [row.status for row in await reservations()] == ["released"]
    async with SessionLocal() as session:
        log = (await session.scalars(select(RequestLog))).one()
        assert log.status == "error" and log.error_code == "usage_unavailable"
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize(
    "invalid_counters",
    [{"input_tokens": True}, {"output_tokens": True}, {"input_tokens_details": {"cached_tokens": True}}],
)
async def test_compact_invalid_observed_counter_remains_upstream_error(
    async_client, provider, monkeypatch, path, invalid_counters
):
    provider.usage_location = "earlier_response"
    provider.earlier_usage_override = {**USAGE, **invalid_counters}
    monkeypatch.setattr(async_client._transport, "raise_app_exceptions", False)
    response = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "invalid_upstream_response"
    assert len(provider.calls) == 1
    assert [row.status for row in await reservations()] == ["released"]
    async with SessionLocal() as session:
        log = (await session.scalars(select(RequestLog))).one()
        assert log.status == "error" and log.error_code == "invalid_upstream_response"
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize(
    "control",
    [
        {"thinking": "minimal"},
        {"reasoning_effort": "minimal"},
        {"thinking": "minimal", "reasoning": {"summary": "auto"}},
        {"reasoning": {"effort": "minimal", "summary": "auto"}},
    ],
)
async def test_compact_preserves_same_provider_reasoning_as_trigger(async_client, provider, path, control):
    changed = await async_client.patch(f"/api/model-sources/{provider.ids[1]}", json={"isEnabled": False})
    assert changed.status_code == 200
    compact = await async_client.post(path, headers=provider.headers, json={**compact_body(), **control})
    trigger = await async_client.post(
        path.removesuffix("/compact"), headers=provider.headers, json={**compact_body(trigger=True), **control}
    )
    assert compact.status_code == trigger.status_code == 200, (compact.text, trigger.text)
    assert len(provider.calls) == 2
    fields = {"thinking", "reasoning_effort", "reasoning"}
    for _, forwarded in provider.calls:
        assert {key: value for key, value in forwarded.items() if key in fields} == control
    assert [row.status for row in await reservations()] == ["finalized", "finalized"]
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize("alias", ["thinking", "reasoning_effort"])
@pytest.mark.parametrize(
    ("policy", "expected_effort"),
    [({"enforcedReasoningEffort": "high"}, "high"), ({"allowedReasoningEfforts": ["minimal"]}, "minimal")],
)
async def test_compact_preserves_policy_required_reasoning(
    async_client, provider, path, alias, policy, expected_effort
):
    key = await async_client.post(
        "/api/api-keys/",
        json={
            "name": "compact-reasoning-policy",
            "assignedSourceIds": [provider.ids[0]],
            "allowedModels": [MODEL],
            **policy,
        },
    )
    assert key.status_code == 200, key.text
    headers = {"Authorization": "Bearer " + key.json()["key"]}
    controls = {alias: "minimal", "reasoning": {"summary": "auto"}}
    compact = await async_client.post(path, headers=headers, json={**compact_body(), **controls})
    trigger = await async_client.post(
        path.removesuffix("/compact"), headers=headers, json={**compact_body(trigger=True), **controls}
    )
    assert compact.status_code == trigger.status_code == 200, (compact.text, trigger.text)
    assert len(provider.calls) == 2
    fields = {"thinking", "reasoning_effort", "reasoning"}
    forwarded_controls = [{key: value for key, value in body.items() if key in fields} for _, body in provider.calls]
    assert forwarded_controls[0] == forwarded_controls[1]
    assert forwarded_controls[0]["reasoning"] == {"effort": expected_effort, "summary": "auto"}


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize("mode", ["malformed_error_root", "malformed_error_nested"])
async def test_compact_malformed_error_is_upstream_failure(async_client, provider, monkeypatch, path, mode):
    provider.mode = mode
    monkeypatch.setattr(async_client._transport, "raise_app_exceptions", False)
    response = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert response.status_code == 502, response.text
    expected = "invalid_upstream_response" if mode == "malformed_error_root" else "upstream_error"
    assert response.json()["error"]["code"] == expected
    assert len(provider.calls) == 1
    assert [row.status for row in await reservations()] == ["released"]
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)
    async with SessionLocal() as session:
        log = (await session.scalars(select(RequestLog))).one()
        assert log.status == "error" and log.error_code == expected
        assert log.model_source_id == provider.ids[0] and log.upstream_status_code == 200


@pytest.mark.parametrize("path", COMPACT_PATHS + RESPONSE_PATHS)
@pytest.mark.parametrize("slash", ["", "/"])
async def test_source_compaction_routes_alias_and_records_usage(async_client, provider, path, slash):
    response = await async_client.post(
        path + slash, headers=provider.headers, json=compact_body(trigger=path in RESPONSE_PATHS)
    )
    if slash and path in COMPACT_PATHS:
        assert response.status_code == 405
        assert not provider.calls and not await reservations()
        return
    assert response.status_code == 200, response.text
    token, forwarded = provider.calls[0]
    assert token == "Bearer token-compact-0"
    assert forwarded["model"] == "upstream-model"
    assert forwarded["input"] == compact_body(trigger=True)["input"]
    assert forwarded["stream"] is True and forwarded["store"] is False
    assert "upstream-model" not in response.text
    assert "cipher-source" in response.text and "cmp_source" in response.text
    if path in COMPACT_PATHS:
        result = response.json()
        assert result["object"] == "response.compaction"
        assert result["model"] == MODEL
        assert result["usage"] == USAGE
        assert len(result["output"]) == 1
    else:
        assert "response.completed" in response.text
    rows = await reservations()
    assert len(rows) == 1 and rows[0].status == "finalized"
    async with SessionLocal() as session:
        log = (await session.scalars(select(RequestLog))).one()
        assert log.model_source_id == provider.ids[0] and log.account_id is None
        assert log.model_source_revision and log.request_kind == "compaction"
        assert (log.input_tokens, log.output_tokens, log.cached_input_tokens, log.reasoning_tokens) == (21, 8, 10, 3)
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS + RESPONSE_PATHS)
async def test_compact_output_continues_on_another_replica_and_rejects_changed_owner(
    async_client, provider, monkeypatch, path
):
    response = await async_client.post(
        path, headers=provider.headers, json=compact_body(trigger=path in RESPONSE_PATHS)
    )
    assert response.status_code == 200
    monkeypatch.setattr(source_pool, "_SOURCE_POOL", source_pool.SourcePool())
    monkeypatch.setattr(source_pool.random, "choice", lambda values: values[-1])
    followup = compact_body()
    followup["input"] = [
        {"type": "compaction", "id": "cmp_source", "encrypted_content": "cipher-source"},
        {"role": "user", "content": "Continue"},
    ]
    response = await async_client.post("/v1/responses", headers=provider.headers, json=followup)
    assert response.status_code == 200, response.text
    assert [call[0] for call in provider.calls] == ["Bearer token-compact-0"] * 2
    changed = await async_client.patch(f"/api/model-sources/{provider.ids[0]}", json={"apiKey": "replacement-token"})
    assert changed.status_code == 200
    response = await async_client.post(
        path,
        headers=provider.headers,
        json={
            **followup,
            "input": followup["input"] + ([{"type": "compaction_trigger"}] if path in RESPONSE_PATHS else []),
        },
    )
    assert response.status_code == 409, response.text
    assert len(provider.calls) == 2 and len(await reservations()) == 2


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize(
    "mode", ["failed", "truncated", "missing_item", "invalid_envelope", "item_done", "summary", "invalid_item_id"]
)
async def test_compact_terminal_contract_and_cleanup(async_client, provider, path, mode):
    provider.mode = mode
    response = await async_client.post(path, headers=provider.headers, json=compact_body())
    success = mode in ("item_done", "summary", "invalid_item_id")
    assert response.status_code == (200 if success else 502), response.text
    if success:
        item = response.json()["output"][0]
        assert item["type"] == "compaction" and item["encrypted_content"] == "cipher-source"
        assert item["status"] == "completed"
        assert item.get("id") == (None if mode == "invalid_item_id" else "cmp_source")
    else:
        assert "error" in response.json() and "cipher-source" not in response.text
    assert len(provider.calls) == 1
    rows = await reservations()
    assert len(rows) == 1 and rows[0].status == ("finalized" if success else "released")
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS)
async def test_compact_broken_stream_returns_upstream_error_without_replay(async_client, provider, monkeypatch, path):
    from app.modules.proxy import api

    provider.mode = "broken_connection"
    original = api.stream_source_responses

    async def open_then_abort(*args, **kwargs):
        stream = await original(*args, **kwargs)
        provider.abort_requested.set()
        return stream

    monkeypatch.setattr(api, "stream_source_responses", open_then_abort)
    response = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "model_source_unreachable"
    assert response.json()["error"]["type"] == "upstream_error"
    assert len(provider.calls) == 1
    assert [row.status for row in await reservations()] == ["released"]
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)
    async with SessionLocal() as session:
        log = (await session.scalars(select(RequestLog))).one()
        assert log.status == "error" and log.error_code == "model_source_unreachable"
        assert log.model_source_id == provider.ids[0] and log.account_id is None
        assert log.model_source_revision and log.request_kind == "compaction"
        assert log.upstream_status_code == 200


@pytest.mark.parametrize("path", COMPACT_PATHS + RESPONSE_PATHS)
async def test_compact_disabled_source_denied_before_dispatch(async_client, provider, path):
    for source_id in provider.ids:
        await async_client.patch(f"/api/model-sources/{source_id}", json={"isEnabled": False})
    response = await async_client.post(
        path, headers=provider.headers, json=compact_body(trigger=path in RESPONSE_PATHS)
    )
    assert response.status_code == 503 and response.json()["error"]["code"] == "model_source_disabled"
    assert not provider.calls and not await reservations()


@pytest.mark.parametrize("path", COMPACT_PATHS + RESPONSE_PATHS)
async def test_unknown_compact_history_never_switches_credentials(async_client, provider, path):
    body = compact_body(trigger=path in RESPONSE_PATHS)
    body["input"].insert(0, {"type": "reasoning", "encrypted_content": "unknown-owner"})
    response = await async_client.post(path, headers=provider.headers, json=body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "model_source_owner_unavailable"
    assert not provider.calls and not await reservations()


@pytest.mark.parametrize("path", COMPACT_PATHS)
async def test_compact_disconnect_closes_source_and_releases_reservation(async_client, provider, path):

    provider.mode = "stall"
    stream = _AsgiStream(
        app=async_client._transport.app, path=path, headers=provider.headers, body=json.dumps(compact_body()).encode()
    )
    task = asyncio.create_task(stream.run())
    try:
        await asyncio.wait_for(provider.entered.wait(), timeout=5)
        stream.disconnect()
        await asyncio.wait_for(task, timeout=10)
        await asyncio.wait_for(provider.closed.wait(), timeout=5)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    rows = await reservations()
    assert len(rows) == 1 and rows[0].status == "released"
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS)
async def test_compact_timeout_closes_source_without_failover(async_client, provider, monkeypatch, path):
    from types import SimpleNamespace

    from app.modules.proxy import api

    provider.mode = "stall"
    original = api.with_dashboard_overrides

    def compact_timeout(settings):
        actual = original(settings)
        return SimpleNamespace(**{**actual.model_dump(), "compact_request_budget_seconds": 0.1})

    monkeypatch.setattr(api, "with_dashboard_overrides", compact_timeout)
    response = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert response.status_code == 504, response.text
    await asyncio.wait_for(provider.closed.wait(), timeout=5)
    assert len(provider.calls) == 1
    assert [row.status for row in await reservations()] == ["released"]
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("failure", ["settlement", "publication"])
async def test_compact_persistence_failure_withholds_state_and_releases_once(
    async_client, provider, monkeypatch, failure
):
    from app.modules.proxy.source_ownership import SourceOwnershipRecorder

    attempts = 0

    async def fail(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("synthetic persistence failure")

    if failure == "settlement":
        monkeypatch.setattr(ApiKeysService, "finalize_usage_reservation", fail)
    else:
        monkeypatch.setattr(SourceOwnershipRecorder, "_commit", fail)
    response = await async_client.post(COMPACT_PATHS[0], headers=provider.headers, json=compact_body())
    assert response.status_code == 502 and "cipher-source" not in response.text
    assert attempts == 1 and len(provider.calls) == 1
    assert [row.status for row in await reservations()] == ["released"]
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS + RESPONSE_PATHS)
async def test_compact_uses_enforced_model_and_source_assignment(async_client, provider, path):
    created = await async_client.post(
        "/api/api-keys/",
        json={
            "name": "forced-compact",
            "enforcedModel": MODEL,
            "assignedSourceIds": [provider.ids[1]],
        },
    )
    assert created.status_code == 200
    response = await async_client.post(
        path,
        headers={"Authorization": "Bearer " + created.json()["key"]},
        json={**compact_body(trigger=path in RESPONSE_PATHS), "model": "gpt-5.1"},
    )
    assert response.status_code == 200, response.text
    assert provider.calls[0][0] == "Bearer token-compact-1"
    assert provider.calls[0][1]["model"] == "upstream-model"


@pytest.mark.parametrize("path", COMPACT_PATHS + RESPONSE_PATHS)
async def test_compact_trigger_validation_preserves_route_contract(async_client, provider, path):
    body = compact_body(trigger=True)
    body["input"].append({"type": "compaction_trigger"})
    response = await async_client.post(path, headers=provider.headers, json=body)
    if path == "/v1/responses/compact":
        assert response.status_code == 200
        assert provider.calls[0][1]["input"] == compact_body(trigger=True)["input"]
    else:
        assert response.status_code == 400 and response.json()["error"]["param"] == "input"
        assert not provider.calls and not await reservations()


async def test_large_compact_output_keeps_usage_when_stream_observer_is_bounded(async_client, provider):
    provider.mode = "large"
    response = await async_client.post(COMPACT_PATHS[0], headers=provider.headers, json=compact_body())
    assert response.status_code == 200, response.text[:200]
    assert response.json()["usage"] == USAGE
    assert [row.status for row in await reservations()] == ["finalized"]


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize("anchor", ["previous_response", "turn_state", "file"])
async def test_source_compact_respects_subscription_continuity(async_client, provider, monkeypatch, path, anchor):
    from unittest.mock import AsyncMock

    from app.core.openai.models import CompactResponsePayload
    from app.modules.proxy.service import ProxyService

    payload = compact_body()
    payload["conversation"] = {"id": "conv_subscription"}
    headers = dict(provider.headers)
    subscription = AsyncMock(
        return_value=CompactResponsePayload.model_validate(
            {
                "object": "response.compaction",
                "output": [{"type": "compaction", "encrypted_content": "subscription"}],
            }
        )
    )
    monkeypatch.setattr(ProxyService, "compact_responses", subscription)
    if anchor == "previous_response":
        payload["previous_response_id"] = "resp_subscription"
        monkeypatch.setattr(
            ProxyService, "_resolve_websocket_previous_response_owner", AsyncMock(return_value="account")
        )
    elif anchor == "turn_state":
        headers["x-codex-turn-state"] = "real-subscription-turn"
        monkeypatch.setattr(ProxyService, "_resolve_compact_turn_state_owner", AsyncMock(return_value="account"))
    else:
        payload["input"] = [{"role": "user", "content": [{"type": "input_file", "file_id": "file_pinned"}]}]
    response = await async_client.post(path, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert "subscription" in response.text
    subscription.assert_awaited_once()
    assert subscription.call_args.args[0].model_extra["conversation"] == payload["conversation"]
    assert not provider.calls


@pytest.mark.parametrize("path", COMPACT_PATHS)
async def test_source_compact_validation_error_does_not_fall_back_to_subscription(
    async_client, provider, monkeypatch, path
):
    from unittest.mock import AsyncMock

    from app.modules.proxy.service import ProxyService

    subscription = AsyncMock(side_effect=AssertionError("source validation must not fall back to subscription"))
    monkeypatch.setattr(ProxyService, "compact_responses", subscription)
    payload = {**compact_body(), "conversation": {"id": "conv_source"}}
    response = await async_client.post(path, headers=provider.headers, json=payload)
    assert response.status_code == 400 and response.json()["error"]["param"] == "conversation"
    subscription.assert_not_awaited()
    assert not provider.calls and not await reservations()


@pytest.mark.parametrize("path", COMPACT_PATHS)
async def test_compact_owned_state_rejects_disabled_source_before_reservation(async_client, provider, path):
    first = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert first.status_code == 200
    await async_client.patch(f"/api/model-sources/{provider.ids[0]}", json={"isEnabled": False})
    response = await async_client.post(
        path,
        headers=provider.headers,
        json={
            **compact_body(),
            "input": first.json()["output"],
        },
    )
    assert response.status_code == 409
    assert len(provider.calls) == 1 and len(await reservations()) == 1


@pytest.mark.parametrize("path", COMPACT_PATHS)
@pytest.mark.parametrize("anchor", ["previous_response", "encrypted"])
async def test_compact_source_lookup_miss_retains_ownership_denial(async_client, provider, path, anchor):
    first = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert first.status_code == 200
    for source_id in provider.ids:
        changed = await async_client.patch(f"/api/model-sources/{source_id}", json={"isEnabled": False})
        assert changed.status_code == 200
    body = compact_body()
    if anchor == "previous_response":
        body["previous_response_id"] = "  " + first.json()["id"] + "  "
    else:
        body["input"] = first.json()["output"]
    response = await async_client.post(path, headers=provider.headers, json=body)
    assert response.status_code == 409, response.text
    expected_code = (
        "previous_response_owner_unavailable" if anchor == "previous_response" else "model_source_owner_unavailable"
    )
    assert response.json()["error"]["code"] == expected_code
    assert len(provider.calls) == 1 and len(await reservations()) == 1


@pytest.mark.parametrize("path", COMPACT_PATHS + RESPONSE_PATHS)
async def test_compact_rejects_mixed_source_history(async_client, provider, monkeypatch, path):
    first = await async_client.post(COMPACT_PATHS[0], headers=provider.headers, json=compact_body())
    assert first.status_code == 200
    monkeypatch.setattr(source_pool, "_SOURCE_POOL", source_pool.SourcePool())
    monkeypatch.setattr(source_pool.random, "choice", lambda values: values[-1])
    second = await async_client.post(COMPACT_PATHS[0], headers=provider.headers, json=compact_body())
    assert second.status_code == 200
    assert [call[0] for call in provider.calls] == ["Bearer token-compact-0", "Bearer token-compact-1"]
    body = compact_body(trigger=path in RESPONSE_PATHS)
    body["input"] = first.json()["output"] + second.json()["output"] + body["input"]
    response = await async_client.post(path, headers=provider.headers, json=body)
    assert response.status_code == 409
    assert len(provider.calls) == 2 and len(await reservations()) == 2


async def _subscription_anchor(async_client, *, anchor, api_key_id, body, headers):
    from app.dependencies import get_proxy_service_for_app
    from app.modules.request_logs.repository import RequestLogsRepository
    from tests.integration.test_proxy_compact import _import_account

    account_id = await _import_account(async_client, email="mixed-compact@example.com", raw_account_id="mixed-compact")
    service = get_proxy_service_for_app(async_client._transport.app)
    if anchor == "previous_response":
        async with SessionLocal() as session:
            await RequestLogsRepository(session).add_log(
                account_id=account_id,
                api_key_id=api_key_id,
                request_id="resp_subscription_other",
                model=MODEL,
                input_tokens=None,
                output_tokens=None,
                latency_ms=None,
                status="success",
                error_code=None,
            )
        body["previous_response_id"] = "resp_subscription_other"
    elif anchor == "turn_state":
        coordinator = service._durable_bridge
        claimed = await coordinator.claim_live_session(
            session_key_kind="session_header",
            session_key_value="mixed-subscription-session",
            api_key_id=api_key_id,
            instance_id="mixed-owner-fixture",
            owner_process_epoch="mixed-owner-fixture",
            lease_ttl_seconds=120.0,
            account_id=account_id,
            model=MODEL,
            service_tier=None,
            latest_turn_state=None,
            latest_response_id=None,
            allow_takeover=True,
        )
        await coordinator.register_turn_state(
            session_id=claimed.session_id,
            api_key_id=api_key_id,
            instance_id="mixed-owner-fixture",
            owner_epoch=claimed.owner_epoch,
            turn_state="turn-mixed-subscription",
            lease_ttl_seconds=120.0,
        )
        headers["x-codex-turn-state"] = "turn-mixed-subscription"
    else:
        await service._pin_file_account("file_mixed_subscription", account_id)
        body["input"].insert(
            0, {"role": "user", "content": [{"type": "input_file", "file_id": "file_mixed_subscription"}]}
        )


@pytest.mark.parametrize(
    ("path", "trigger"),
    [(path, False) for path in COMPACT_PATHS + RESPONSE_PATHS] + [(path, True) for path in RESPONSE_PATHS],
)
@pytest.mark.parametrize("anchor", ["previous_response", "turn_state", "file"])
@pytest.mark.parametrize("reference", ["encrypted", "item"])
async def test_compact_state_never_crosses_to_subscription_owner(
    async_client, provider, monkeypatch, path, trigger, anchor, reference
):
    from unittest.mock import AsyncMock

    import app.modules.proxy.service as proxy_service

    first = await async_client.post(COMPACT_PATHS[0], headers=provider.headers, json=compact_body())
    assert first.status_code == 200, first.text
    async with SessionLocal() as session:
        api_key_id = (await session.scalars(select(RequestLog.api_key_id))).one()
    body = compact_body(trigger=trigger)
    compact_item = first.json()["output"][0]
    state = (
        {"type": "compaction", "encrypted_content": compact_item["encrypted_content"]}
        if reference == "encrypted"
        else {"type": "item_reference", "id": compact_item["id"]}
    )
    body["input"].insert(0, state)
    headers = dict(provider.headers)
    await _subscription_anchor(async_client, anchor=anchor, api_key_id=api_key_id, body=body, headers=headers)
    compact = AsyncMock(side_effect=AssertionError("mixed source state must not reach subscription"))
    stream = AsyncMock(side_effect=AssertionError("mixed source state must not reach subscription"))
    monkeypatch.setattr(proxy_service, "core_compact_responses", compact)
    monkeypatch.setattr(proxy_service, "core_stream_responses", stream)
    response = await async_client.post(path, headers=headers, json=body)
    # HTTP Responses uses turn-state account ownership only for compaction.
    # An ordinary source continuation keeps its source and ignores that header.
    source_continuation = anchor == "turn_state" and path in RESPONSE_PATHS and not trigger
    if source_continuation:
        assert response.status_code == 200, response.text
        assert [call[0] for call in provider.calls] == ["Bearer token-compact-0"] * 2
    else:
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] in (
            "previous_response_owner_unavailable",
            "model_source_owner_unavailable",
        )
    compact.assert_not_called()
    stream.assert_not_called()
    attempts = 2 if source_continuation else 1
    assert len(provider.calls) == attempts
    assert [row.status for row in await reservations()] == ["finalized"] * attempts
    assert all(get_source_bulkhead().in_flight(source_id) == 0 for source_id in provider.ids)


@pytest.mark.parametrize("path", COMPACT_PATHS)
async def test_mixed_compact_ownership_lookup_error_fails_before_reservation(async_client, provider, monkeypatch, path):
    from unittest.mock import AsyncMock

    from app.modules.model_sources.ownership_repository import SourceOwnershipRepository
    from app.modules.proxy.service import ProxyService

    first = await async_client.post(path, headers=provider.headers, json=compact_body())
    assert first.status_code == 200
    async with SessionLocal() as session:
        api_key_id = (await session.scalars(select(RequestLog.api_key_id))).one()
    body = {**compact_body(), "input": first.json()["output"]}
    headers = dict(provider.headers)
    await _subscription_anchor(
        async_client, anchor="previous_response", api_key_id=api_key_id, body=body, headers=headers
    )
    monkeypatch.setattr(SourceOwnershipRepository, "find", AsyncMock(side_effect=RuntimeError("lookup unavailable")))
    subscription = AsyncMock(side_effect=AssertionError("ownership lookup must fail closed"))
    monkeypatch.setattr(ProxyService, "compact_responses", subscription)
    response = await async_client.post(path, headers=headers, json=body)
    assert response.status_code == 502 and response.json()["error"]["code"] == "model_source_lookup_failed"
    subscription.assert_not_called()
    assert len(provider.calls) == 1 and len(await reservations()) == 1


@pytest.mark.parametrize("path", COMPACT_PATHS + RESPONSE_PATHS)
async def test_compact_keeps_history_and_trigger_despite_source_input_override(async_client, provider, path):
    metadata = {
        "upstream_model": "upstream-model",
        "source_request_overrides": {"input": [{"role": "user", "content": "Replacement"}], "store": True},
    }
    for source_id in provider.ids:
        updated = await async_client.patch(
            f"/api/model-sources/{source_id}",
            json={"models": [{"model": MODEL, "rawMetadataJson": json.dumps(metadata)}]},
        )
        assert updated.status_code == 200, updated.text
    response = await async_client.post(
        path, headers=provider.headers, json=compact_body(trigger=path in RESPONSE_PATHS)
    )
    assert response.status_code == 200, response.text
    assert provider.calls[0][1]["input"] == compact_body(trigger=True)["input"]
    assert provider.calls[0][1]["store"] is False
