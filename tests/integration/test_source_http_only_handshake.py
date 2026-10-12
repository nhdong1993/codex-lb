"""HTTP-only source keys decline upgrades before the first model frame."""

from __future__ import annotations

import asyncio
import json

import pytest
from aiohttp import web
from sqlalchemy import select

from app.db.models import ApiKeyUsageReservation
from app.db.session import SessionLocal
from app.modules.proxy import api
from tests.integration.model_source_helpers import stub_source_upstreams
from tests.integration.test_model_source_websocket import create_key, create_source
from tests.integration.test_proxy_transient_retry import _import_account

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROUTES = ["/v1/responses", "/v1/responses/", "/backend-api/codex/responses", "/backend-api/codex/responses/"]


async def handshake(app, path, key):
    incoming, outgoing = asyncio.Queue(), asyncio.Queue()
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"localhost"), (b"authorization", f"Bearer {key}".encode())],
        "scheme": "ws",
        "server": ("127.0.0.1", 80),
        "client": ("127.0.0.1", 1234),
        "subprotocols": [],
        "extensions": {"websocket.http.response": {}},
    }
    task = asyncio.create_task(app(scope, incoming.get, outgoing.put))
    try:
        await incoming.put({"type": "websocket.connect"})
        first = await asyncio.wait_for(outgoing.get(), 5)
        if first["type"] == "websocket.http.response.start":
            body = await asyncio.wait_for(outgoing.get(), 5)
            return first["status"], json.loads(body["body"])
        assert first["type"] == "websocket.accept", first
        return 101, None
    finally:
        await incoming.put({"type": "websocket.disconnect", "code": 1000})
        try:
            await asyncio.wait_for(task, 5)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("path", ROUTES)
async def test_http_only_key_denies_upgrade_without_reserving_and_http_succeeds(async_client, app_instance, path):
    calls = []

    async def provider(request):
        calls.append(request.method)
        return web.json_response(
            {
                "id": "resp_http_only",
                "object": "response",
                "model": "source-ws-model",
                "status": "completed",
                "output": [],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )

    async with stub_source_upstreams() as start:
        source_id = await create_source(async_client, await start(provider), enabled=False)
        key = await create_key(async_client, source_id)
        status, body = await handshake(app_instance, path, key["key"])
        assert status == 426
        assert body["error"]["code"] == "websocket_upstream_transport_unavailable"
        assert calls == []
        async with SessionLocal() as session:
            assert (await session.execute(select(ApiKeyUsageReservation))).scalars().all() == []
        response = await async_client.post(
            path,
            headers={"Authorization": f"Bearer {key['key']}"},
            json={"model": "source-ws-model", "input": "hello", "stream": False},
        )
        assert response.status_code == 200, response.text
        assert response.json()["id"] == "resp_http_only"
        assert calls == ["POST"]


@pytest.mark.parametrize("scope", ["capable", "mixed"])
async def test_capable_source_and_mixed_keys_keep_websocket(async_client, app_instance, scope):
    source_id = await create_source(async_client, "http://127.0.0.1:9/v1", enabled=scope == "capable")
    key = await create_key(async_client, source_id)
    if scope == "mixed":
        account_id = await _import_account(async_client, "mixed-account", "mixed@example.test")
        response = await async_client.patch(f"/api/api-keys/{key['id']}", json={"assignedAccountIds": [account_id]})
        assert response.status_code == 200, response.text
    assert (await handshake(app_instance, "/v1/responses", key["key"]))[0] == 101


@pytest.mark.parametrize("path", ROUTES)
async def test_source_capability_failure_returns_sanitized_503(async_client, app_instance, monkeypatch, path):
    source_id = await create_source(async_client, "http://127.0.0.1:9/v1", enabled=False)
    key = await create_key(async_client, source_id)

    async def fail(_):
        raise RuntimeError("private-driver-credentials")

    monkeypatch.setattr(api, "source_only_key_supports_websockets", fail)
    status, body = await handshake(app_instance, path, key["key"])
    assert status == 503
    assert body["error"]["code"] == "upstream_unavailable"
    assert "private-driver" not in json.dumps(body)


async def test_invalid_key_is_denied_before_transport_lookup(async_client, app_instance, monkeypatch):
    source_id = await create_source(async_client, "http://127.0.0.1:9/v1", enabled=False)
    await create_key(async_client, source_id)

    async def unexpected(_):
        pytest.fail("invalid key must not reach source transport lookup")

    monkeypatch.setattr(api, "source_only_key_supports_websockets", unexpected)
    assert (await handshake(app_instance, "/v1/responses", "invalid-key"))[0] == 401
