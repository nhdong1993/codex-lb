"""Source models advertise the Fast (priority) service tier declared in their metadata."""

from __future__ import annotations

import json

import pytest
from aiohttp import web

from tests.integration.model_source_helpers import _create_model_source, stub_source_upstreams
from tests.integration.test_model_source_websocket import create_key

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

RESPONSES_PATHS = ["/v1/responses", "/v1/responses/", "/backend-api/codex/responses", "/backend-api/codex/responses/"]
FAST_SERVICE_TIERS = [{"id": "priority", "name": "Fast", "description": "Priority processing"}]
FAST_METADATA = json.dumps({"service_tiers": FAST_SERVICE_TIERS, "additional_speed_tiers": ["fast"]})


@pytest.fixture
async def source_upstream():
    async with stub_source_upstreams() as start:
        yield start


def _recording_responses_handler(seen: list[dict[str, object]]):
    async def handler(request: web.Request) -> web.Response:
        seen.append(await request.json())
        body = (
            b'data: {"type":"response.created","response":{"id":"resp_fast","status":"in_progress","output":[]}}\n\n'
            b'data: {"type":"response.completed","response":{"id":"resp_fast","status":"completed","output":[],'
            b'"usage":{"input_tokens":2,"output_tokens":1,"total_tokens":3}}}\n\n'
        )
        return web.Response(body=body, headers={"Content-Type": "text/event-stream"})

    return handler


def _catalog_entry(payload: dict[str, object], key: str, slug: str) -> dict[str, object]:
    entries = payload[key]
    assert isinstance(entries, list)
    return next(entry for entry in entries if entry.get("slug", entry.get("id")) == slug)


async def test_declared_fast_tier_reaches_every_client_catalog(async_client):
    source_id = await _create_model_source(
        async_client,
        name="fast",
        model="fast-model",
        base_url="http://127.0.0.1:9/v1",
        supports_responses=True,
        raw_metadata_json=FAST_METADATA,
    )
    key = await create_key(async_client, source_id)
    headers = {"Authorization": f"Bearer {key['key']}"}

    for path in ("/backend-api/codex/models", "/api/key-dashboard/models"):
        response = await async_client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        entry = _catalog_entry(response.json(), "models", "fast-model")
        assert entry["service_tiers"] == FAST_SERVICE_TIERS
        assert entry["additional_speed_tiers"] == ["fast"]

    response = await async_client.get("/v1/models", headers=headers)
    assert response.status_code == 200, response.text
    metadata = _catalog_entry(response.json(), "data", "fast-model")["metadata"]
    assert metadata["service_tiers"] == FAST_SERVICE_TIERS
    assert metadata["additional_speed_tiers"] == ["fast"]


async def test_undeclared_source_model_advertises_no_tier(async_client):
    await _create_model_source(
        async_client,
        name="plain",
        model="plain-model",
        base_url="http://127.0.0.1:9/v1",
        supports_responses=True,
    )

    response = await async_client.get("/backend-api/codex/models")
    assert response.status_code == 200, response.text
    entry = _catalog_entry(response.json(), "models", "plain-model")
    assert entry.get("service_tiers") is None
    assert entry.get("additional_speed_tiers") is None


@pytest.mark.parametrize("path", RESPONSES_PATHS)
async def test_priority_tier_is_forwarded_to_the_source(async_client, source_upstream, path):
    seen: list[dict[str, object]] = []
    base_url = await source_upstream(_recording_responses_handler(seen))
    await _create_model_source(
        async_client,
        name="fast",
        model="fast-model",
        base_url=base_url,
        supports_responses=True,
        raw_metadata_json=FAST_METADATA,
    )

    response = await async_client.post(
        path,
        json={"model": "fast-model", "instructions": "hi", "input": [], "stream": True, "service_tier": "priority"},
    )

    assert response.status_code == 200, response.text
    assert len(seen) == 1
    assert seen[0]["service_tier"] == "priority"
