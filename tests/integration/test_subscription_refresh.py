from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, update

from app.core.auth.dependencies import require_dashboard_write_access
from app.core.clients.subscriptions import SubscriptionFetchError
from app.core.crypto import TokenEncryptor
from app.core.exceptions import DashboardPermissionError
from app.core.upstream_proxy import UpstreamProxyRouteError
from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus
from app.db.session import SessionLocal
from app.modules.accounts import subscription_scheduler as scheduler
from app.modules.accounts import subscription_service as service
from app.modules.accounts.repository import AccountsRepository
from app.modules.accounts.subscription_repository import SubscriptionRepository

pytestmark = pytest.mark.integration
DEADLINE = datetime(2026, 10, 4, 4, 36, 34, tzinfo=UTC)


async def seed(account_id="internal-id", *, status=AccountStatus.ACTIVE):
    claim = {
        "https://api.openai.com/auth": {
            "chatgpt_plan_type": "plus",
            "chatgpt_account_id": "chatgpt-id",
            "chatgpt_subscription_active_until": "2026-09-04T04:36:34Z",
        }
    }
    token = "header." + base64.urlsafe_b64encode(json.dumps(claim).encode()).decode().rstrip("=") + ".sig"
    enc = TokenEncryptor()
    async with SessionLocal() as session:
        session.add(
            Account(
                id=account_id,
                email=f"{account_id}@example.com",
                chatgpt_account_id="chatgpt-id",
                plan_type="plus",
                status=status,
                last_refresh=utcnow(),
                access_token_encrypted=enc.encrypt("secret-access"),
                refresh_token_encrypted=enc.encrypt("secret-refresh"),
                id_token_encrypted=enc.encrypt(token),
            )
        )
        await session.commit()
    return account_id


@pytest.fixture
def upstream(monkeypatch):
    fetch, route = AsyncMock(return_value=DEADLINE), AsyncMock(return_value=None)
    monkeypatch.setattr(service, "fetch_subscription_term", fetch)
    monkeypatch.setattr(service, "resolve_upstream_route", route)
    return fetch, route


@pytest.mark.asyncio
async def test_renewal_refreshes_paused_account_and_both_dashboard_paths(async_client, upstream):
    account_id = await seed(status=AccountStatus.PAUSED)
    fetch, route = upstream
    await service.refresh_subscription(account_id)
    assert route.call_args.kwargs["account_id"] == account_id
    assert fetch.call_args.kwargs["account_id"] == "chatgpt-id"
    for path in ["/api/accounts", f"/api/accounts/{account_id}/summary", f"/api/accounts/{account_id}/summary/"]:
        response = await async_client.get(path)
        assert response.status_code == 200
        summary = response.json()["accounts"][0] if path == "/api/accounts" else response.json()
        assert summary["subscription"]["activeUntil"] == "2026-10-04T04:36:34Z"
        assert summary["subscription"]["source"] == "subscriptions_api"
        assert datetime.fromisoformat(summary["subscription"]["lastCheckedAt"]).utcoffset() == timedelta(0)
        assert summary["status"] == "paused"
        assert "secret-access" not in response.text
        assert "secret-refresh" not in response.text
    await service.refresh_subscription(account_id)
    fetch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["", "/"])
async def test_manual_refresh_bypasses_daily_claim_and_returns_summary(async_client, upstream, suffix):
    account_id = await seed()
    fetch, route = upstream
    await service.refresh_subscription(account_id)
    async with SessionLocal() as session:
        await session.execute(update(Account).values(subscription_attempted_at=utcnow() - timedelta(hours=1)))
        await session.commit()
    response = await async_client.post(f"/api/accounts/{account_id}/subscription/refresh{suffix}")
    assert response.status_code == 200
    assert response.json()["subscription"]["activeUntil"] == "2026-10-04T04:36:34Z"
    assert fetch.await_count == 2
    assert route.await_count == 2


@pytest.mark.asyncio
async def test_daily_refresh_skips_recent_attempt_and_refreshes_after_24_hours(async_client, upstream):
    account_id = await seed()
    async with SessionLocal() as session:
        await session.execute(update(Account).values(subscription_attempted_at=utcnow() - timedelta(hours=23)))
        await session.commit()
    await scheduler.SubscriptionRefreshScheduler().refresh_due()
    upstream[0].assert_not_awaited()
    async with SessionLocal() as session:
        await session.execute(update(Account).values(subscription_attempted_at=utcnow() - timedelta(hours=25)))
        await session.commit()
    await scheduler.SubscriptionRefreshScheduler().refresh_due()
    upstream[0].assert_awaited_once()
    assert (await async_client.get(f"/api/accounts/{account_id}/summary")).json()["subscription"][
        "source"
    ] == "subscriptions_api"


@pytest.mark.asyncio
async def test_manual_failure_preserves_snapshot_and_repeated_click_is_throttled(async_client, upstream):
    account_id = await seed()
    await service.refresh_subscription(account_id)
    before = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()["subscription"]
    async with SessionLocal() as session:
        await session.execute(update(Account).values(subscription_attempted_at=utcnow() - timedelta(hours=1)))
        await session.commit()
    upstream[0].side_effect = SubscriptionFetchError("http_error", 403)
    response = await async_client.post(f"/api/accounts/{account_id}/subscription/refresh")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "subscription_refresh_failed"
    assert "secret" not in response.text
    repeated = await async_client.post(f"/api/accounts/{account_id}/subscription/refresh")
    assert repeated.status_code == 409
    assert upstream[0].await_count == 2
    after = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()["subscription"]
    assert after == before


@pytest.mark.asyncio
async def test_manual_refresh_requires_write_access_and_handles_missing_account(app_instance, async_client, upstream):
    response = await async_client.post("/api/accounts/missing/subscription/refresh")
    assert response.status_code == 404

    async def deny_write():
        raise DashboardPermissionError("Read only", code="read_only_access")

    app_instance.dependency_overrides[require_dashboard_write_access] = deny_write
    try:
        response = await async_client.post("/api/accounts/missing/subscription/refresh/")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "read_only_access"
    finally:
        app_instance.dependency_overrides.pop(require_dashboard_write_access, None)
    upstream[0].assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_failure_preserves_last_success(async_client, upstream):
    account_id = await seed()
    fetch, _ = upstream
    await service.refresh_subscription(account_id)
    before = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()["subscription"]
    async with SessionLocal() as session:
        await session.execute(update(Account).values(subscription_attempted_at=utcnow() - timedelta(days=2)))
        await session.commit()
    fetch.side_effect = RuntimeError("secret-upstream-error")
    await scheduler.SubscriptionRefreshScheduler().refresh_due()
    after = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()
    assert after["subscription"] == before
    assert after["status"] == "active"


@pytest.mark.asyncio
async def test_explicit_inactive_suppresses_old_token_without_status_change(async_client, upstream):
    account_id = await seed()
    upstream[0].return_value = None
    await service.refresh_subscription(account_id)
    data = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()
    assert data["subscription"]["activeUntil"] is None
    assert data["subscription"]["source"] == "subscriptions_api"
    assert data["status"] == "active"
    assert data["planType"] == "plus"


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["credential", "identity", "plan", "delete", "superseded", "deactivate"])
async def test_inflight_result_cannot_overwrite_replaced_source(async_client, upstream, mutation):
    account_id = await seed()

    async def change_during_fetch(**kwargs):
        async with SessionLocal() as session:
            if mutation == "delete":
                await session.execute(delete(Account).where(Account.id == account_id))
            else:
                values = {
                    "credential": {"access_token_encrypted": TokenEncryptor().encrypt("replacement")},
                    "identity": {"chatgpt_account_id": "replacement"},
                    "plan": {"plan_type": "pro"},
                    "superseded": {"subscription_attempted_at": utcnow() + timedelta(seconds=1)},
                    "deactivate": {"status": AccountStatus.DEACTIVATED},
                }[mutation]
                await session.execute(update(Account).where(Account.id == account_id).values(**values))
            await session.commit()
        return DEADLINE

    upstream[0].side_effect = change_during_fetch
    await service.refresh_subscription(account_id)
    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is None or account.subscription_checked_at is None


@pytest.mark.asyncio
async def test_saved_snapshot_is_ignored_after_credential_change(async_client, upstream):
    account_id = await seed()
    await service.refresh_subscription(account_id)
    async with SessionLocal() as session:
        await session.execute(update(Account).values(access_token_encrypted=TokenEncryptor().encrypt("replacement")))
        await session.commit()
    data = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()
    assert data["subscription"]["source"] == "id_token"
    assert data["subscription"]["activeUntil"] == "2026-09-04T04:36:34Z"


@pytest.mark.asyncio
@pytest.mark.parametrize("active_until", [DEADLINE, None])
async def test_routine_rotation_preserves_subscription_and_daily_clock(async_client, upstream, active_until):
    account_id = await seed()
    upstream[0].return_value = active_until
    await service.refresh_subscription(account_id)
    before = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()["subscription"]
    enc = TokenEncryptor()
    for rotation in range(2):
        async with SessionLocal() as session:
            account = await session.get(Account, account_id)
            assert account is not None
            attempted_at = account.subscription_attempted_at
            assert await AccountsRepository(session).rotate_tokens(
                account_id,
                access_token_encrypted=enc.encrypt(f"rotated-access-{rotation}"),
                refresh_token_encrypted=enc.encrypt(f"rotated-refresh-{rotation}"),
                id_token_encrypted=enc.encrypt("no-subscription-claims"),
                last_refresh=utcnow(),
                expected_refresh_token_encrypted=account.refresh_token_encrypted,
                plan_type=account.plan_type,
                chatgpt_account_id=account.chatgpt_account_id,
            )
            await session.refresh(account)
            assert account.subscription_attempted_at == attempted_at
        for path in ["/api/accounts", f"/api/accounts/{account_id}/summary"]:
            response = await async_client.get(path)
            assert response.status_code == 200
            data = response.json()["accounts"][0] if path == "/api/accounts" else response.json()
            assert data["subscription"] == before
    await scheduler.SubscriptionRefreshScheduler().refresh_due()
    upstream[0].assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_snapshot", ["absent", "unmatched"])
@pytest.mark.parametrize("active_until", [DEADLINE, None])
async def test_snapshot_saved_between_rotation_read_and_write_survives(
    async_client, upstream, monkeypatch, initial_snapshot, active_until
):
    account_id = await seed()
    now = utcnow()
    async with SessionLocal() as session:
        source = await SubscriptionRepository(session).claim(account_id, attempted_at=now, cutoff=now)
        assert source is not None
        if initial_snapshot == "unmatched":
            await session.execute(
                update(Account)
                .where(Account.id == account_id)
                .values(subscription_checked_at=now - timedelta(days=1), subscription_fingerprint="replaced-source")
            )
            await session.commit()
    enc = TokenEncryptor()
    async with SessionLocal() as session:
        original_scalar = session.scalar

        async def save_after_read(statement, *args, **kwargs):
            current = await original_scalar(statement, *args, **kwargs)
            async with SessionLocal() as writer:
                assert await SubscriptionRepository(writer).save(source, active_until=active_until, checked_at=now)
            return current

        monkeypatch.setattr(session, "scalar", save_after_read)
        assert await AccountsRepository(session).rotate_tokens(
            account_id,
            access_token_encrypted=enc.encrypt("rotated-access"),
            refresh_token_encrypted=enc.encrypt("rotated-refresh"),
            id_token_encrypted=enc.encrypt("no-subscription-claims"),
            last_refresh=now,
            expected_refresh_token_encrypted=source.refresh_token_encrypted,
            plan_type=source.plan_type,
            chatgpt_account_id=source.chatgpt_account_id,
        )
    for path in ["/api/accounts", f"/api/accounts/{account_id}/summary"]:
        response = await async_client.get(path)
        assert response.status_code == 200
        data = response.json()["accounts"][0] if path == "/api/accounts" else response.json()
        assert data["subscription"]["source"] == "subscriptions_api"
        assert data["subscription"]["activeUntil"] == ("2026-10-04T04:36:34Z" if active_until else None)
        assert datetime.fromisoformat(data["subscription"]["lastCheckedAt"]).replace(tzinfo=None) == now
    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        assert account.subscription_attempted_at == now
    await scheduler.SubscriptionRefreshScheduler().refresh_due()
    upstream[0].assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["credential", "identity", "plan", "refresh", "workspace", "user"])
async def test_rotation_does_not_rebind_a_source_replaced_after_read(async_client, upstream, monkeypatch, change):
    account_id = await seed()
    await service.refresh_subscription(account_id)
    before = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()["subscription"]
    enc = TokenEncryptor()
    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        expected = account.refresh_token_encrypted
        original_scalar = session.scalar

        async def replace_after_read(statement, *args, **kwargs):
            current = await original_scalar(statement, *args, **kwargs)
            values = {
                "credential": {"access_token_encrypted": enc.encrypt("replaced-access")},
                "identity": {"chatgpt_account_id": "replaced-identity"},
                "plan": {"plan_type": "pro"},
                "refresh": {"refresh_token_encrypted": enc.encrypt("replaced-refresh")},
                "workspace": {"workspace_id": "replaced-workspace"},
                "user": {"chatgpt_user_id": "replaced-user"},
            }[change]
            async with SessionLocal() as writer:
                await writer.execute(update(Account).where(Account.id == account_id).values(**values))
                await writer.commit()
            return current

        monkeypatch.setattr(session, "scalar", replace_after_read)
        applied = await AccountsRepository(session).rotate_tokens(
            account_id,
            access_token_encrypted=enc.encrypt("rotated-access"),
            refresh_token_encrypted=enc.encrypt("rotated-refresh"),
            id_token_encrypted=enc.encrypt("no-subscription-claims"),
            last_refresh=utcnow(),
            expected_refresh_token_encrypted=expected,
        )
        assert applied is (change != "refresh")
    data = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()
    if change == "refresh":
        assert data["subscription"] == before
    else:
        assert data["subscription"]["source"] != "subscriptions_api"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["plan", "identity", "credential", "lost_cas"])
async def test_rotation_does_not_authorize_an_unmatched_snapshot(async_client, upstream, change):
    account_id = await seed()
    await service.refresh_subscription(account_id)
    before = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()["subscription"]
    enc = TokenEncryptor()
    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        if change == "credential":
            account.access_token_encrypted = enc.encrypt("replacement")
            await session.commit()
        applied = await AccountsRepository(session).rotate_tokens(
            account_id,
            access_token_encrypted=enc.encrypt("rotated-access"),
            refresh_token_encrypted=enc.encrypt("rotated-refresh"),
            id_token_encrypted=enc.encrypt("no-subscription-claims"),
            last_refresh=utcnow(),
            expected_refresh_token_encrypted=(
                enc.encrypt("stale-refresh") if change == "lost_cas" else account.refresh_token_encrypted
            ),
            plan_type="pro" if change == "plan" else account.plan_type,
            chatgpt_account_id="changed-identity" if change == "identity" else account.chatgpt_account_id,
        )
        assert applied is (change != "lost_cas")
    data = (await async_client.get(f"/api/accounts/{account_id}/summary")).json()
    if change == "lost_cas":
        assert data["subscription"] == before
    else:
        assert data["subscription"]["source"] != "subscriptions_api"


@pytest.mark.asyncio
async def test_route_failure_never_sends_direct_request(async_client, upstream):
    account_id = await seed()
    upstream[1].side_effect = UpstreamProxyRouteError("pool_unavailable")
    await scheduler.SubscriptionRefreshScheduler().refresh_due()
    upstream[0].assert_not_awaited()
    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        assert account.status == AccountStatus.ACTIVE
        assert account.subscription_attempted_at is not None
        assert account.subscription_checked_at is None


@pytest.mark.asyncio
async def test_workers_bound_partial_failure_and_own_sessions(async_client, upstream):
    for i in range(8):
        await seed(str(i))
    active = peak = calls = 0

    async def fetch(**kwargs):
        nonlocal active, peak, calls
        active += 1
        calls += 1
        fails = calls == 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        if fails:
            raise RuntimeError("one failure")
        return DEADLINE

    upstream[0].side_effect = fetch
    await scheduler.SubscriptionRefreshScheduler().refresh_due()
    assert upstream[0].await_count == 8
    assert peak <= 3
    async with SessionLocal() as session:
        successful = 0
        for i in range(8):
            a = await session.get(Account, str(i))
            assert a is not None
            successful += a.subscription_checked_at is not None
        assert successful == 7


@pytest.mark.asyncio
async def test_stop_cancels_and_awaits_workers(async_client, upstream, monkeypatch):
    for i in range(4):
        await seed(str(i))
    entered = asyncio.Event()
    active = 0

    async def fetch(**kwargs):
        nonlocal active
        active += 1
        if active == 3:
            entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1

    upstream[0].side_effect = fetch

    class Leader:
        async def run_if_leader(self, fn):
            return await fn()

    monkeypatch.setattr(scheduler, "_get_leader_election", lambda: Leader())
    runner = scheduler.SubscriptionRefreshScheduler()
    await runner.start()
    await asyncio.wait_for(entered.wait(), 2)
    await asyncio.wait_for(runner.stop(), 2)
    assert active == 0
    assert runner._task is None


@pytest.mark.asyncio
async def test_followers_and_ineligible_accounts_make_no_requests(async_client, upstream, monkeypatch):
    for status in [AccountStatus.DEACTIVATED, AccountStatus.REAUTH_REQUIRED]:
        await seed(status.value, status=status)
    await seed("free")
    async with SessionLocal() as session:
        await session.execute(update(Account).where(Account.id == "free").values(plan_type="free"))
        await session.commit()
    await scheduler.SubscriptionRefreshScheduler().refresh_due()
    upstream[0].assert_not_awaited()
    await seed("eligible")
    invoked = asyncio.Event()

    class Follower:
        async def run_if_leader(self, fn):
            invoked.set()
            return None

    monkeypatch.setattr(scheduler, "_get_leader_election", lambda: Follower())
    runner = scheduler.SubscriptionRefreshScheduler()
    await runner.start()
    await asyncio.wait_for(invoked.wait(), 2)
    await runner.stop()
    upstream[0].assert_not_awaited()
