"""Independent HTTP requests stop returning to a persistently failing soft owner."""

from __future__ import annotations

import pytest

import app.modules.proxy.service as proxy_module
from tests.integration.test_proxy_transient_retry import (
    _extract_events,
    _import_account,
    _sse_event,
    _success_sse_event,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

PROCESSING_ERROR = (
    "An error occurred while processing your request. You can retry your request, "
    "or contact us through our help center at help.openai.com if the error persists."
)


@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize("error_code", ["server_is_overloaded", "server_error"])
async def test_next_soft_affinity_request_leaves_sustained_failure_before_isolation(
    async_client, monkeypatch, path, error_code
):
    await _import_account(async_client, "overload_owner", "owner@example.test")
    seen = []

    async def stream(payload, headers, access_token, account_id, **kwargs):
        seen.append(account_id)
        if account_id == "overload_owner" and len(seen) in {1, 3, 5}:
            yield _sse_event(
                {
                    "type": "response.failed",
                    "response": {
                        "error": {
                            "code": error_code,
                            "message": PROCESSING_ERROR if error_code == "server_error" else "Servers overloaded",
                        }
                    },
                }
            )
        else:
            yield _success_sse_event(f"resp_soft_{len(seen)}")

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "stream": True,
        "prompt_cache_key": "overload-soft-affinity",
    }
    for index in range(5):
        response = await async_client.post(path, json=payload)
        assert response.status_code == 200
        events = _extract_events(response.text.splitlines())
        assert events[-1]["type"] == ("response.failed" if index % 2 == 0 else "response.completed")
        assert len(seen) == index + 1, "a terminal response must not be silently replayed"
        if index == 0:
            await _import_account(async_client, "overload_sibling", "sibling@example.test")

    assert seen == ["overload_owner"] * 5
    response = await async_client.post(path, json=payload)
    assert response.status_code == 200
    assert _extract_events(response.text.splitlines())[-1]["type"] == "response.completed"
    assert seen[-1] == "overload_sibling"
    response = await async_client.post(path, json=payload)
    assert response.status_code == 200
    assert seen[-2:] == ["overload_sibling", "overload_sibling"]
