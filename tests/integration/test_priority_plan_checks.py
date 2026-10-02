from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, update

from app.core.auth.refresh import RefreshError
from app.core.clients.subscriptions import SubscriptionFetchError
from app.core.clients.usage import UsageFetchError
from app.core.crypto import TokenEncryptor
from app.core.usage.models import UsagePayload
from app.core.utils.time import utcnow
from app.db.models import Account, AccountPlanCheck, AccountStatus
from app.db.session import SessionLocal
from app.modules.accounts import subscription_service
from app.modules.accounts.repository import AccountsRepository
from app.modules.usage import plan_check_scheduler, plan_checks, updater
from app.modules.usage.plan_check_scheduler import PlanCheckScheduler
from app.modules.usage.plan_checks import PlanCheckRepository
from app.modules.usage.plan_downgrade_observations import (
    PlanDowngradeObservationStore,
    credential_fingerprint,
    discard_plan_downgrade_observations,
)

pytestmark = pytest.mark.integration


async def seed(account_id="paid") -> Account:
    enc = TokenEncryptor()
    async with SessionLocal() as session:
        account = Account(
            id=account_id,
            email=f"{account_id}@example.com",
            chatgpt_account_id=f"upstream-{account_id}",
            plan_type="plus",
            status=AccountStatus.ACTIVE,
            last_refresh=utcnow(),
            access_token_encrypted=enc.encrypt("access"),
            refresh_token_encrypted=enc.encrypt("refresh"),
            id_token_encrypted=enc.encrypt("id"),
        )
        session.add(account)
        await session.commit()
        session.expunge(account)
        return account


def payload(plan="free"):
    return UsagePayload.model_validate(
        {
            "plan_type": plan,
            "rate_limit": {"primary_window": {"used_percent": 0, "limit_window_seconds": 2592000}},
        }
    )


@pytest.fixture
def upstream(monkeypatch):
    fetch = AsyncMock(return_value=payload())
    monkeypatch.setattr(updater, "fetch_usage", fetch)
    monkeypatch.setattr(updater, "_resolve_upstream_route_for_account", AsyncMock(return_value=None))
    monkeypatch.setattr(subscription_service, "resolve_upstream_route", AsyncMock(return_value=None))
    monkeypatch.setattr(subscription_service, "fetch_subscription_term", AsyncMock(return_value=None))
    return fetch


async def make_due():
    async with SessionLocal() as session:
        await session.execute(update(AccountPlanCheck).values(next_attempt_at=utcnow() - timedelta(seconds=1)))
        await session.commit()


async def check_row(account_id="paid"):
    async with SessionLocal() as session:
        return await session.get(AccountPlanCheck, account_id)


async def test_first_free_schedules_followup_and_api_masks_old_term(async_client, upstream):
    account = await seed()
    runner = updater.build_background_usage_updater()
    result = await runner.force_refresh_result(account, ignore_refresh_disabled=True)
    assert not result.fetch_succeeded
    row = await check_row()
    assert row is not None
    assert timedelta(seconds=14) < row.next_attempt_at - row.requested_at <= timedelta(seconds=15)
    for path in ["/api/accounts", "/api/accounts/paid/summary", "/api/accounts/paid/summary/"]:
        response = await async_client.get(path)
        assert response.status_code == 200
        summary = response.json()["accounts"][0] if path == "/api/accounts" else response.json()
        assert summary["planType"] == "plus"
        assert summary["planCheckPending"] is True
        assert summary["status"] == "active"
    await make_due()
    await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert summary["planType"] == "free"
    assert summary["planCheckPending"] is False
    assert summary["subscription"]["activeUntil"] is None
    assert summary["status"] == "active"
    async with SessionLocal() as session:
        saved = await session.get(Account, account.id)
        assert saved is not None
        assert saved.refresh_token_encrypted == account.refresh_token_encrypted
        assert saved.access_token_encrypted == account.access_token_encrypted
    assert upstream.await_count == 2


async def test_claims_coalesce_across_replicas_and_cannot_reset_budget(db_setup):
    account = await seed()

    async def request():
        async with SessionLocal() as session:
            return await PlanCheckRepository(session).request(account, model="gpt-test")

    assert sum(await asyncio.gather(request(), request(), request())) == 1

    async def claim():
        async with SessionLocal() as session:
            return await PlanCheckRepository(session).claim_due()

    claims = await asyncio.gather(claim(), claim(), claim())
    assert sum(map(len, claims)) == 1
    original = await check_row()
    assert not await request()
    current = await check_row()
    assert (current.generation, current.requested_at, current.attempts) == (
        original.generation,
        original.requested_at,
        1,
    )


@pytest.mark.parametrize("subscription_fails", [False, True])
async def test_endpoint_partial_failure_is_bounded_and_preserves_health(
    async_client, upstream, monkeypatch, subscription_fails
):
    account = await seed()
    await plan_checks.request_plan_check(account, model="gpt-test")
    if subscription_fails:
        monkeypatch.setattr(
            subscription_service,
            "fetch_subscription_term",
            AsyncMock(side_effect=SubscriptionFetchError("http_error", 403)),
        )
    else:
        upstream.side_effect = UsageFetchError(503, "unavailable")
    for _ in range(4):
        await make_due()
        await PlanCheckScheduler().refresh_due()
    assert upstream.await_count == (2 if subscription_fails else 3)
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert summary["status"] == "active"
    assert summary["planType"] == ("free" if subscription_fails else "plus")
    if not subscription_fails:
        assert summary["subscription"]["source"] == "subscriptions_api"
        assert summary["subscription"]["activeUntil"] is None


async def test_paid_sample_clears_pending_without_reauthentication(async_client, upstream):
    account = await seed()
    await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    upstream.return_value = payload("plus")
    await make_due()
    await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["status"], summary["planCheckPending"]) == ("plus", "active", False)
    assert await PlanDowngradeObservationStore().get(account.id) is None


async def test_replacement_during_fetch_rejects_stale_plan_and_observation(async_client, upstream):
    account = await seed()
    await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)

    async def replace_during_fetch(**kwargs):
        async with SessionLocal() as session:
            await discard_plan_downgrade_observations(session, account.id)
            await session.execute(
                update(Account)
                .where(Account.id == account.id)
                .values(
                    refresh_token_encrypted=TokenEncryptor().encrypt("replacement"),
                    credential_generation=Account.credential_generation + 1,
                    plan_type="plus",
                )
            )
            await session.commit()
        return payload()

    upstream.side_effect = replace_during_fetch
    await make_due()
    await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["status"], summary["planCheckPending"]) == ("plus", "active", False)
    assert await check_row() is None
    assert await PlanDowngradeObservationStore().get(account.id) is None
    await plan_checks.request_plan_check(account, model="gpt-test")
    assert await check_row() is None  # delayed enqueue from the old credential


async def test_replaced_generation_cannot_write_metadata_or_evidence(db_setup):
    account = await seed()
    await plan_checks.request_plan_check(account, model="gpt-test")
    old = await check_row()
    async with SessionLocal() as session:
        await session.execute(delete(AccountPlanCheck))
        await session.commit()
    await plan_checks.request_plan_check(account, model="gpt-test")
    async with SessionLocal() as session:
        assert not await AccountsRepository(session).update_account_metadata(
            account.id,
            plan_type="free",
            expected_plan_check_generation=old.generation,
            expected_refresh_token_encrypted=account.refresh_token_encrypted,
        )
    assert (
        await PlanDowngradeObservationStore().observe(
            account.id,
            credential_fingerprint=credential_fingerprint(account),
            observed_plan_type="free",
            plan_check_generation=old.generation,
        )
        == 0
    )


async def test_model_exclusion_is_specific_expires_and_preserves_required_owner(async_client):
    from app.dependencies import get_proxy_service_for_app

    account = await seed()
    await seed("other")
    await plan_checks.request_plan_check(account, model="gpt-test")
    assert await plan_checks.rejected_model_account_ids([account], "gpt-test") == {account.id}
    assert await plan_checks.rejected_model_account_ids([account], "another") == set()
    service = get_proxy_service_for_app(async_client._transport.app)
    movable = await service._load_balancer.select_account(model="gpt-test")
    assert movable.account.id == "other"
    pinned = await service._load_balancer.select_account(
        model="gpt-test",
        required_account_id=account.id,
        required_account_is_ownership_constraint=True,
    )
    assert pinned.account is None
    continuity = await service._load_balancer.select_account(
        model="gpt-test",
        required_account_id=account.id,
        required_continuity_owner=True,
    )
    assert continuity.account is None
    async with SessionLocal() as session:
        await session.execute(update(AccountPlanCheck).values(requested_at=utcnow() - timedelta(minutes=3)))
        await session.commit()
    assert await plan_checks.rejected_model_account_ids([account], "gpt-test") == set()


async def test_shutdown_cancels_and_awaits_workers(db_setup, monkeypatch):
    account = await seed()
    await plan_checks.request_plan_check(account, model="gpt-test")
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def wait_forever(*args, **kwargs):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    monkeypatch.setattr(plan_check_scheduler, "refresh_subscription", wait_forever)
    scheduler = PlanCheckScheduler()
    await scheduler.start()
    await asyncio.wait_for(started.wait(), 3)
    await scheduler.stop()
    assert cancelled.is_set()
    assert scheduler._task is None


@pytest.mark.parametrize("permanent", [False, True])
async def test_only_permanent_refresh_failure_requires_reauth(async_client, upstream, monkeypatch, permanent):
    from app.modules.accounts import auth_manager

    account = await seed()
    await plan_checks.request_plan_check(account, model="gpt-test")
    upstream.side_effect = UsageFetchError(401, "revoked access", code="token_revoked")
    monkeypatch.setattr(auth_manager, "resolve_upstream_route", AsyncMock(return_value=None))
    monkeypatch.setattr(
        auth_manager,
        "refresh_access_token",
        AsyncMock(
            side_effect=RefreshError(
                "refresh_token_invalidated" if permanent else "transport_error",
                "failed",
                permanent,
                transport_error=not permanent,
            )
        ),
    )
    await PlanCheckScheduler().refresh_due()
    async with SessionLocal() as session:
        saved = await session.get(Account, account.id)
        assert saved is not None
        assert saved.status == (AccountStatus.REAUTH_REQUIRED if permanent else AccountStatus.ACTIVE)
        assert saved.plan_type == "plus"


async def test_workspace_guard_survives_priority_confirmation(async_client, upstream):
    account = await seed()
    async with SessionLocal() as session:
        await session.execute(update(Account).where(Account.id == account.id).values(workspace_id="team"))
        await session.commit()
    account.workspace_id = "team"
    await plan_checks.request_plan_check(account, model="gpt-test")
    for _ in range(3):
        await make_due()
        await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert summary["planType"] == "plus"
    assert summary["status"] == "active"
    assert await PlanDowngradeObservationStore().get(account.id) is None


async def test_unrecognized_priority_sample_retries_without_losing_first_free(db_setup, upstream):
    account = await seed()
    await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    upstream.return_value = payload("mystery")
    await make_due()
    await PlanCheckScheduler().refresh_due()
    assert not (await check_row()).completed
    observation = await PlanDowngradeObservationStore().get(account.id)
    assert observation is not None
    assert observation.observations == 1
    upstream.return_value = payload("free")
    await make_due()
    await PlanCheckScheduler().refresh_due()
    async with SessionLocal() as session:
        saved = await session.get(Account, account.id)
        assert saved is not None
        assert saved.plan_type == "free"


async def test_routine_token_rotation_keeps_queued_confirmation(db_setup, upstream):
    account = await seed()
    await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    queued = await check_row()
    enc = TokenEncryptor()
    rotated_refresh = enc.encrypt("rotated-refresh")
    async with SessionLocal() as session:
        assert await AccountsRepository(session).rotate_tokens(
            account.id,
            enc.encrypt("rotated-access"),
            rotated_refresh,
            enc.encrypt("rotated-id"),
            utcnow(),
            expected_refresh_token_encrypted=account.refresh_token_encrypted,
        )
    assert (await check_row()).generation == queued.generation
    await make_due()
    await PlanCheckScheduler().refresh_due()
    async with SessionLocal() as session:
        saved = await session.get(Account, account.id)
        assert saved is not None
        assert saved.plan_type == "free"
        assert saved.refresh_token_encrypted == rotated_refresh
        assert saved.status == AccountStatus.ACTIVE


async def test_stale_permanent_error_cannot_reauth_repaired_account(db_setup, upstream):
    account = await seed()
    await plan_checks.request_plan_check(account, model="gpt-test")

    async def replace_during_fetch(**kwargs):
        async with SessionLocal() as session:
            await discard_plan_downgrade_observations(session, account.id)
            await session.execute(
                update(Account)
                .where(Account.id == account.id)
                .values(
                    refresh_token_encrypted=TokenEncryptor().encrypt("replacement"),
                    credential_generation=Account.credential_generation + 1,
                )
            )
            await session.commit()
        raise UsageFetchError(401, "Old token invalidated", code="token_invalidated")

    upstream.side_effect = replace_during_fetch
    await PlanCheckScheduler().refresh_due()
    async with SessionLocal() as session:
        saved = await session.get(Account, account.id)
        assert saved is not None
        assert saved.status == AccountStatus.ACTIVE
        assert saved.plan_type == "plus"


async def test_scheduler_bounds_fanout_and_isolates_worker_failure(db_setup, upstream, monkeypatch):
    accounts = [await seed(f"paid-{index}") for index in range(4)]
    for account in accounts:
        await plan_checks.request_plan_check(account, model="gpt-test")
    monkeypatch.setattr(plan_check_scheduler, "refresh_subscription", AsyncMock())

    async def fetch(**kwargs):
        if kwargs["account_id"] == accounts[0].chatgpt_account_id:
            raise UsageFetchError(503, "unavailable")
        return payload("plus")

    upstream.side_effect = fetch
    await PlanCheckScheduler().refresh_due()
    rows = [await check_row(account.id) for account in accounts]
    assert upstream.await_count == 3
    assert [row.attempts for row in rows] == [1, 1, 1, 0]
    assert [row.completed for row in rows] == [False, True, True, False]
