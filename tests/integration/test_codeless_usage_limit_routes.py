"""Route-level regressions for code-less upstream usage-limit terminals.

Covers the HTTP stream route (``/backend-api/codex/responses``):
- owner-pinned ``previous_response_id`` turns rewrite the code-less form exactly like the coded one
- an ``invalid_request_error`` quoting usage-limit wording is not treated as quota
- keyed API-key reservations settle before the deferred usage-limit health write
"""

from __future__ import annotations

import base64
import json

import pytest
from sqlalchemy import select

import app.modules.proxy.service as proxy_module
from app.core.auth import generate_unique_account_id
from app.core.clients.proxy import ProxyResponseError
from app.db.models import Account, AccountStatus, ApiKeyUsageReservation
from app.db.session import SessionLocal
from app.dependencies import get_proxy_service_for_app
from app.modules.usage.updater import UsageUpdater

pytestmark = pytest.mark.integration

_CODELESS_USAGE_LIMIT = {"message": "The usage limit has been reached"}
_CODED_USAGE_LIMIT = {"code": "usage_limit_reached", "message": "The usage limit has been reached"}
# A reservation is open while ``reserved``/``settling``; a successful stream finalizes it.
_CLOSED_RESERVATION_STATUSES = frozenset({"finalized", "settled", "released"})
_ECHOED_USAGE_LIMIT_MESSAGE = "Invalid 'input[0].content': unsupported text \"The usage limit has been reached\"."


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"header.{body}.sig"


def _make_auth_json(account_id: str, email: str) -> dict:
    payload = {
        "email": email,
        "chatgpt_account_id": account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    return {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access-token",
            "refreshToken": "refresh-token",
            "accountId": account_id,
        },
    }


async def _import_account(async_client, account_id: str, email: str) -> str:
    auth_json = _make_auth_json(account_id, email)
    files = {"auth_json": ("auth.json", json.dumps(auth_json), "application/json")}
    response = await async_client.post("/api/accounts/import", files=files)
    assert response.status_code == 200
    return generate_unique_account_id(account_id, email)


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _success_sse_event(response_id: str) -> str:
    return _sse_event(
        {
            "type": "response.completed",
            "response": {"id": response_id, "usage": {"input_tokens": 1, "output_tokens": 1}},
        }
    )


def _extract_events(lines: list[str]) -> list[dict]:
    return [json.loads(line[6:]) for line in lines if line.startswith("data: ") and line[6:] != "[DONE]"]


def _failed_error_codes(events: list[dict]) -> list[str | None]:
    return [event["response"]["error"].get("code") for event in events if event.get("type") == "response.failed"]


def _record_usage_refresh_requests(monkeypatch) -> list[str]:
    requested: list[str] = []

    def fake_request_refresh(account_id: str) -> None:
        requested.append(account_id)
        return None

    monkeypatch.setattr(UsageUpdater, "request_refresh", staticmethod(fake_request_refresh))
    return requested


async def _account_status(account_id: str) -> AccountStatus:
    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        return account.status


@pytest.mark.asyncio
@pytest.mark.parametrize("frame_error", [_CODELESS_USAGE_LIMIT, _CODED_USAGE_LIMIT], ids=["code-less", "coded"])
async def test_pinned_previous_response_usage_limit_frame_rewrites_owner_unavailable(
    async_client, monkeypatch, frame_error
):
    """An owner-pinned turn cannot move, so both usage-limit forms surface the owner rewrite.

    The code-less frame previously raised a retryable error, excluded the owner and failed
    selection closed with a fresh ``upstream_error`` and an account-less request log.
    """
    owner_id = await _import_account(async_client, "acc_codeless_pinned_owner", "codeless-pinned-owner@example.com")
    sibling_id = await _import_account(
        async_client, "acc_codeless_pinned_sibling", "codeless-pinned-sibling@example.com"
    )
    refreshes = _record_usage_refresh_requests(monkeypatch)
    seen_account_ids: list[str | None] = []

    async def fake_owner(self, *, previous_response_id, api_key, session_id=None, surface):
        del self, previous_response_id, api_key, session_id, surface
        return owner_id

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False):
        seen_account_ids.append(account_id)
        yield _sse_event({"type": "response.failed", "response": {"id": "resp_pinned_limit", "error": frame_error}})

    monkeypatch.setattr(proxy_module.ProxyService, "_resolve_websocket_previous_response_owner", fake_owner)
    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "stream": True,
        "previous_response_id": "resp_pinned_previous",
    }
    async with async_client.stream("POST", "/backend-api/codex/responses", json=payload) as resp:
        assert resp.status_code == 200
        lines = [line async for line in resp.aiter_lines() if line]

    events = _extract_events(lines)
    failed = [event for event in events if event.get("type") == "response.failed"]
    assert len(failed) == 1
    assert failed[0]["response"]["error"]["code"] == "previous_response_owner_unavailable"
    assert failed[0]["response"]["error"]["message"] == "Previous response owner account is unavailable; retry later."
    assert seen_account_ids == ["acc_codeless_pinned_owner"]
    assert await _account_status(owner_id) == AccountStatus.RATE_LIMITED
    assert await _account_status(sibling_id) == AccountStatus.ACTIVE
    assert refreshes == [owner_id]


@pytest.mark.asyncio
@pytest.mark.parametrize("delivery", ["http_400", "terminal_frame"])
async def test_invalid_request_quoting_usage_limit_wording_is_not_quota(async_client, monkeypatch, delivery):
    """An explicit request-shaped code keeps its classification even when it echoes quota wording."""
    account_ids = [
        await _import_account(async_client, f"acc_echoed_limit_{letter}", f"echoed-limit-{letter}@example.com")
        for letter in ("a", "b")
    ]
    refreshes = _record_usage_refresh_requests(monkeypatch)
    seen_account_ids: list[str | None] = []

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False):
        seen_account_ids.append(account_id)
        if len(seen_account_ids) > 1:
            yield _success_sse_event("resp_echoed_limit_retry")
            return
        if delivery == "http_400":
            raise ProxyResponseError(
                400,
                {
                    "error": {
                        "message": _ECHOED_USAGE_LIMIT_MESSAGE,
                        "type": "invalid_request_error",
                        "param": "input",
                    }
                },
                failure_phase="status",
            )
        yield _sse_event(
            {
                "type": "response.failed",
                "response": {
                    "id": "resp_echoed_limit",
                    "error": {"code": "invalid_request_error", "message": _ECHOED_USAGE_LIMIT_MESSAGE},
                },
            }
        )

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    payload = {"model": "gpt-5.1", "instructions": "hi", "input": [], "stream": True}
    async with async_client.stream("POST", "/backend-api/codex/responses", json=payload) as resp:
        body = (await resp.aread()).decode()

    if delivery == "http_400":
        assert resp.status_code == 400
        assert json.loads(body)["error"] == {
            "message": _ECHOED_USAGE_LIMIT_MESSAGE,
            "type": "invalid_request_error",
            "param": "input",
        }
    else:
        assert resp.status_code == 200
        assert _failed_error_codes(_extract_events(body.splitlines())) == ["invalid_request_error"]
    assert "usage_limit_reached" not in body
    assert len(seen_account_ids) == 1
    for account_id in account_ids:
        assert await _account_status(account_id) == AccountStatus.ACTIVE
    assert refreshes == []


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["sibling_retry", "final_account", "after_visible"])
async def test_keyed_codeless_usage_limit_settles_reservation_before_health(
    async_client, app_instance, monkeypatch, scenario
):
    """The code-less usage-limit health write runs only after the API-key reservation closes."""
    letters = ("a", "b") if scenario == "sibling_retry" else ("a",)
    account_ids = {
        f"acc_keyed_codeless_{letter}": await _import_account(
            async_client, f"acc_keyed_codeless_{letter}", f"keyed-codeless-{letter}@example.test"
        )
        for letter in letters
    }
    configured = await async_client.put("/api/settings", json={"apiKeyAuthEnabled": True})
    assert configured.status_code == 200
    created = await async_client.post(
        "/api/api-keys/",
        json={
            "name": "keyed-codeless-usage-limit",
            "limits": [{"limitType": "total_tokens", "limitWindow": "weekly", "maxValue": 1_000_000}],
        },
    )
    assert created.status_code == 200
    key_id = created.json()["id"]
    service = get_proxy_service_for_app(app_instance)
    original_health = service._handle_stream_error
    statuses_at_health: list[str] = []

    async def health(account, error, code, http_status=None, **kwargs):
        if error.get("message") == _CODELESS_USAGE_LIMIT["message"]:
            async with SessionLocal() as session:
                statuses = list(
                    await session.scalars(
                        select(ApiKeyUsageReservation.status).where(ApiKeyUsageReservation.api_key_id == key_id)
                    )
                )
            assert statuses and all(status in _CLOSED_RESERVATION_STATUSES for status in statuses)
            statuses_at_health.extend(statuses)
        return await original_health(account, error, code, http_status=http_status, **kwargs)

    monkeypatch.setattr(service, "_handle_stream_error", health)
    seen_account_ids: list[str | None] = []

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False):
        seen_account_ids.append(account_id)
        if len(seen_account_ids) > 1:
            yield _success_sse_event("resp_keyed_codeless_retry")
            return
        if scenario == "after_visible":
            yield _sse_event({"type": "response.created", "response": {"id": "resp_keyed_codeless"}})
        yield _sse_event({"type": "response.failed", "response": {"error": _CODELESS_USAGE_LIMIT}})

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    payload = {"model": "gpt-5.1", "instructions": "hi", "input": [], "stream": True}
    async with async_client.stream(
        "POST",
        "/backend-api/codex/responses",
        json=payload,
        headers={"Authorization": f"Bearer {created.json()['key']}"},
    ) as resp:
        assert resp.status_code == 200
        lines = [line async for line in resp.aiter_lines() if line]
    assert await service.drain_persistence_tasks(timeout_seconds=5)

    events = _extract_events(lines)
    completed = [event for event in events if event.get("type") == "response.completed"]
    if scenario == "sibling_retry":
        assert len(completed) == 1
        assert _failed_error_codes(events) == []
        assert len(seen_account_ids) == 2
        assert len(set(seen_account_ids)) == 2
    else:
        assert completed == []
        assert len(_failed_error_codes(events)) == 1
        assert seen_account_ids == ["acc_keyed_codeless_a"]
    assert statuses_at_health
    first_account = seen_account_ids[0]
    assert first_account is not None
    assert await _account_status(account_ids[first_account]) == AccountStatus.RATE_LIMITED
