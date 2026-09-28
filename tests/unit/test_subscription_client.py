from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.clients import subscriptions
from app.core.clients.subscriptions import SubscriptionFetchError, fetch_subscription_term, parse_subscription_term
from app.core.upstream_proxy import ResolvedProxyEndpoint, ResolvedUpstreamRoute

pytestmark = pytest.mark.unit
DEADLINE = datetime(2026, 10, 4, 4, 36, 34, tzinfo=UTC)


@pytest.mark.parametrize(
    "payload",
    [
        {"plan_type": "plus", "is_active": True, "active_until": "2026-10-04T04:36:34Z"},
        {"active_until": "2026-10-04T11:36:34+07:00"},
        {"active_until": "2026-10-04T04:36:34"},
        {"subscriptions": [{"status": "trialing", "active_until": DEADLINE.timestamp()}]},
        [{"active": False, "active_until": 2000000000}, {"active": True, "active_until": DEADLINE.timestamp()}],
    ],
)
def test_parses_explicit_subscription_deadlines(payload):
    assert parse_subscription_term(payload, account_id="account", plan_type="plus") == DEADLINE


@pytest.mark.parametrize(
    "payload",
    [
        {"is_active": False, "active_until": "2030-01-01T00:00:00Z"},
        {"active": False},
        {"plan_type": "free"},
        {"status": "expired"},
    ],
)
def test_confirmed_inactive_has_no_term(payload):
    assert parse_subscription_term(payload, account_id="account", plan_type="plus") is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"subscriptions": []},
        {"exp": 2000000000},
        {"data": {"active_until": 2000000000}},
        {"active_until": True},
        {"active_until": float("inf")},
        {"active_until": -1},
        {"active_until": "2026-10-04"},
        {"active_until": "bad"},
        {"active_until": None},
        {"active_until": "0001-01-01T00:00:00+12:00"},
        {"plan_type": "pro", "active_until": 2000000000},
        {"account_id": "other", "active_until": 2000000000},
        {"is_active": "false", "active_until": 2000000000},
        {"status": "unknown", "active_until": 2000000000},
    ],
)
def test_invalid_or_unrelated_payload_does_not_confirm_a_term(payload):
    with pytest.raises(SubscriptionFetchError):
        parse_subscription_term(payload, account_id="account", plan_type="plus")


def fake_transport(monkeypatch, status=200):
    response = MagicMock(status_code=status)
    response.json.return_value = {"plan_type": "plus", "active_until": DEADLINE.isoformat()}
    client = AsyncMock()
    client.get.return_value = response
    client.__aenter__.return_value = client
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(subscriptions, "AsyncSession", factory)
    return factory, client


@pytest.mark.asyncio
async def test_browser_transport_and_exact_account_proxy(monkeypatch):
    factory, client = fake_transport(monkeypatch)
    route = ResolvedUpstreamRoute("account_bound", "pool", ResolvedProxyEndpoint("ep", "http", "proxy.test", 8080))
    assert (
        await fetch_subscription_term(
            access_token="secret-token", account_id="account/one", plan_type="plus", route=route
        )
        == DEADLINE
    )
    assert factory.call_args.kwargs == {
        "impersonate": "chrome136",
        "proxy": "http://proxy.test:8080",
        "timeout": 20,
        "verify": True,
        "allow_redirects": False,
        "trust_env": False,
    }
    client.get.assert_awaited_once_with(
        "https://chatgpt.com/backend-api/subscriptions?account_id=account%2Fone",
        headers={
            "Accept": "*/*",
            "Authorization": "Bearer secret-token",
            "chatgpt-account-id": "account/one",
            "x-openai-target-path": "/backend-api/subscriptions",
            "x-openai-target-route": "/backend-api/subscriptions",
        },
    )
    client.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_direct_route_requires_explicit_resolution(monkeypatch):
    factory, _ = fake_transport(monkeypatch)
    with pytest.raises(ValueError):
        await fetch_subscription_term(access_token="secret", account_id="acc", plan_type="plus", route=None)
    factory.assert_not_called()
    await fetch_subscription_term(
        access_token="secret", account_id="acc", plan_type="plus", route=None, allow_direct_egress=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
async def test_http_errors_do_not_read_or_expose_payload(monkeypatch, status):
    _, client = fake_transport(monkeypatch, status)
    with pytest.raises(SubscriptionFetchError) as error:
        await fetch_subscription_term(
            access_token="secret", account_id="acc", plan_type="plus", route=None, allow_direct_egress=True
        )
    assert error.value.status_code == status
    assert str(error.value) == "http_error"
    client.get.return_value.json.assert_not_called()


@pytest.mark.asyncio
async def test_errors_are_sanitized_and_cancellation_closes_session(monkeypatch):
    _, client = fake_transport(monkeypatch)
    client.get.side_effect = RuntimeError("secret-token proxy-password")
    with pytest.raises(SubscriptionFetchError, match="request_failed") as error:
        await fetch_subscription_term(
            access_token="secret", account_id="acc", plan_type="plus", route=None, allow_direct_egress=True
        )
    assert "secret" not in str(error.value)
    client.get.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await fetch_subscription_term(
            access_token="secret", account_id="acc", plan_type="plus", route=None, allow_direct_egress=True
        )
    assert client.__aexit__.await_count == 2
