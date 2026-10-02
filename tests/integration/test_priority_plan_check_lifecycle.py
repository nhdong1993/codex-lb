from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, text, update

from app.core.auth.refresh import TokenRefreshResult
from app.core.clients.usage import UsageFetchError
from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountPlanCheck, AccountPlanDowngradeObservation, AccountStatus
from app.db.session import SessionLocal
from app.modules.accounts import auth_manager
from app.modules.accounts.background_repository import BackgroundAccountsRepository
from app.modules.accounts.repository import AccountsRepository
from app.modules.usage import plan_check_scheduler, plan_checks, updater
from app.modules.usage.plan_check_lock import lock_plan_check_account
from app.modules.usage.plan_check_scheduler import PlanCheckScheduler
from app.modules.usage.plan_checks import PlanCheckRepository
from app.modules.usage.plan_downgrade_observations import (
    PlanDowngradeObservationStore,
    credential_fingerprint,
    discard_plan_downgrade_observations,
)
from tests.integration.test_priority_plan_checks import check_row, make_due, payload, seed
from tests.integration.test_priority_plan_checks import upstream as upstream  # noqa: F401

pytestmark = pytest.mark.integration


async def test_free_after_completed_paid_check_reopens_remaining_budget(async_client, upstream):
    account = await seed()
    upstream.return_value = payload("plus")
    await plan_checks.request_plan_check(account, model="gpt-test")
    await PlanCheckScheduler().refresh_due()
    old = await check_row()
    assert old is not None and old.completed and old.attempts == 1
    upstream.return_value = payload("free")
    await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    reopened = await check_row()
    assert reopened is not None and not reopened.completed
    assert reopened.generation != old.generation
    assert (reopened.requested_at, reopened.attempts) == (old.requested_at, old.attempts)
    assert (await async_client.get("/api/accounts/paid/summary")).json()["planCheckPending"]
    async with SessionLocal() as session:
        await PlanCheckRepository(session).finish(old, complete=True)
        assert not await PlanCheckRepository(session).request(account, model="another-model")
    still_pending = await check_row()
    assert still_pending is not None and not still_pending.completed
    assert still_pending.next_attempt_at == reopened.next_attempt_at
    await make_due()
    await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["status"], summary["planCheckPending"]) == ("free", "active", False)


async def test_exhausted_completed_check_cannot_reopen(db_setup, upstream):
    account = await seed()
    await plan_checks.request_plan_check(account, model="gpt-test")
    async with SessionLocal() as session:
        await session.execute(update(AccountPlanCheck).values(completed=True, attempts=3))
        await session.commit()
    old = await check_row()
    await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    current = await check_row()
    assert current is not None and old is not None
    assert current.completed and current.attempts == 3
    assert (current.generation, current.requested_at) == (old.generation, old.requested_at)


async def test_free_between_paid_sample_and_completion_keeps_followup(async_client, upstream, monkeypatch):
    account = await seed()
    upstream.return_value = payload("plus")
    await plan_checks.request_plan_check(account, model="gpt-test")
    original = await check_row()
    real_finish = PlanCheckRepository.finish

    async def finish_after_free(self, claim, *, complete):
        assert complete
        upstream.return_value = payload("free")
        await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
        await real_finish(self, claim, complete=complete)

    monkeypatch.setattr(PlanCheckRepository, "finish", finish_after_free)
    await PlanCheckScheduler().refresh_due()
    pending = await check_row()
    assert pending is not None and original is not None
    assert pending.generation != original.generation
    assert pending.requested_at == original.requested_at and pending.attempts == 1
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["planCheckPending"]) == ("plus", True)
    monkeypatch.setattr(PlanCheckRepository, "finish", real_finish)
    await make_due()
    await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["planCheckPending"]) == ("free", False)


@pytest.mark.parametrize("replace_after_conflict", [False, True])
async def test_confirmed_free_survives_rotation_write_conflict(
    async_client, upstream, monkeypatch, replace_after_conflict
):
    account = await seed()
    await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    # Leave only the confirming attempt and one retry in the original budget.
    async with SessionLocal() as session:
        await session.execute(update(AccountPlanCheck).values(attempts=1))
        await session.commit()
    original = await check_row()
    real_sync = updater.UsageUpdater._sync_identity_metadata
    rotated = False
    enc = TokenEncryptor()

    async def rotate_then_sync(self, target, sample):
        nonlocal rotated
        if self._plan_check_generation is not None and not rotated:
            rotated = True
            async with SessionLocal() as session:
                assert await AccountsRepository(session).rotate_tokens(
                    target.id,
                    enc.encrypt("rotated-access"),
                    enc.encrypt("rotated-refresh"),
                    enc.encrypt("rotated-id"),
                    utcnow(),
                    expected_refresh_token_encrypted=target.refresh_token_encrypted,
                )
        return await real_sync(self, target, sample)

    monkeypatch.setattr(updater.UsageUpdater, "_sync_identity_metadata", rotate_then_sync)
    await make_due()
    await PlanCheckScheduler().refresh_due()
    pending = await check_row()
    assert original is not None and pending is not None
    assert pending.generation == original.generation and pending.attempts == 2 and not pending.completed
    evidence = await PlanDowngradeObservationStore().get(account.id)
    assert evidence is not None and evidence.observations == 2
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["status"], summary["planCheckPending"]) == ("plus", "active", True)
    if replace_after_conflict:
        async with SessionLocal() as session:
            # Same replacement boundary used by import/reauth; a matching seat
            # fingerprint must not revive observations from replaced tokens.
            replacement = Account(
                id=account.id,
                email=account.email,
                chatgpt_account_id=account.chatgpt_account_id,
                plan_type="plus",
                status=AccountStatus.ACTIVE,
                access_token_encrypted=enc.encrypt("new-access"),
                refresh_token_encrypted=enc.encrypt("new-refresh"),
                id_token_encrypted=enc.encrypt("new-id"),
                last_refresh=utcnow(),
            )
            assert await AccountsRepository(session).replace_reauthorized(account.id, replacement) is not None
    await make_due()
    await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["status"], summary["planCheckPending"]) == (
        "plus" if replace_after_conflict else "free",
        "active",
        False,
    )
    assert await PlanDowngradeObservationStore().get(account.id) is None
    if not replace_after_conflict:
        completed = await check_row()
        assert completed is not None and completed.completed and completed.attempts == 3
        assert completed.generation == original.generation and completed.requested_at == original.requested_at
    async with SessionLocal() as session:
        saved = await session.get(Account, account.id)
        assert saved is not None
        assert enc.decrypt(saved.refresh_token_encrypted) == (
            "new-refresh" if replace_after_conflict else "rotated-refresh"
        )


async def test_ordinary_confirmation_cannot_clear_replacement_evidence(async_client, upstream, monkeypatch):
    account = await seed()
    runner = updater.build_background_usage_updater()
    await runner.force_refresh_result(account, ignore_refresh_disabled=True)
    real_clear = PlanDowngradeObservationStore.clear
    replaced = False
    enc = TokenEncryptor()

    async def clear_after_replacement(self, account_id, **kwargs):
        nonlocal replaced
        if not replaced and kwargs.get("plan_check_generation") is None:
            replaced = True
            async with SessionLocal() as session:
                saved = await session.get(Account, account_id)
                assert saved is not None and saved.plan_type == "free"
                replacement = Account(
                    id=account_id,
                    email=account.email,
                    chatgpt_account_id=account.chatgpt_account_id,
                    plan_type="plus",
                    status=AccountStatus.ACTIVE,
                    access_token_encrypted=enc.encrypt("new-access"),
                    refresh_token_encrypted=enc.encrypt("new-refresh"),
                    id_token_encrypted=enc.encrypt("new-id"),
                    last_refresh=utcnow(),
                )
                fresh = await AccountsRepository(session).replace_reauthorized(account_id, replacement)
                assert fresh is not None
                session.expunge(fresh)
            await self.observe(
                account_id, credential_fingerprint=credential_fingerprint(fresh), observed_plan_type="free"
            )
            await plan_checks.request_plan_check(fresh)
        await real_clear(self, account_id, **kwargs)

    monkeypatch.setattr(PlanDowngradeObservationStore, "clear", clear_after_replacement)
    await runner.force_refresh_result(account, ignore_refresh_disabled=True)
    assert replaced
    evidence = await PlanDowngradeObservationStore().get(account.id)
    assert evidence is not None and evidence.observations == 1
    upstream.side_effect = [UsageFetchError(502, "temporary"), UsageFetchError(502, "temporary"), payload()]
    for _ in range(3):
        await make_due()
        await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["status"], summary["planCheckPending"]) == ("free", "active", False)
    assert await PlanDowngradeObservationStore().get(account.id) is None
    async with SessionLocal() as session:
        saved = await session.get(Account, account.id)
        assert saved is not None and enc.decrypt(saved.refresh_token_encrypted) == "new-refresh"


async def test_priority_first_free_keeps_its_generation_and_delayed_retry(async_client, upstream):
    account = await seed()
    await plan_checks.request_plan_check(account, model="gpt-test")
    original = await check_row()
    await PlanCheckScheduler().refresh_due()
    pending = await check_row()
    assert original is not None and pending is not None
    assert pending.generation == original.generation
    assert not pending.completed and pending.attempts == 1
    assert 0 < (pending.next_attempt_at - utcnow()).total_seconds() <= 15
    await make_due()
    await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["planCheckPending"]) == ("free", False)


@pytest.mark.parametrize("priority", [False, True])
async def test_paid_sample_clears_free_evidence_across_rotation(async_client, upstream, monkeypatch, priority):
    account = await seed()
    await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    real_clear = PlanDowngradeObservationStore.clear
    rotated = False
    enc = TokenEncryptor()

    async def rotate_before_clear(self, account_id, **kwargs):
        nonlocal rotated
        if not rotated:
            rotated = True
            async with SessionLocal() as session:
                assert await AccountsRepository(session).rotate_tokens(
                    account_id,
                    enc.encrypt("rotated-access"),
                    enc.encrypt("rotated-refresh"),
                    enc.encrypt("rotated-id"),
                    utcnow(),
                    expected_refresh_token_encrypted=account.refresh_token_encrypted,
                )
        await real_clear(self, account_id, **kwargs)

    monkeypatch.setattr(PlanDowngradeObservationStore, "clear", rotate_before_clear)
    upstream.return_value = payload("plus")
    if priority:
        await make_due()
        await PlanCheckScheduler().refresh_due()
    else:
        await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    assert rotated and await PlanDowngradeObservationStore().get(account.id) is None
    async with SessionLocal() as session:
        fresh = await session.get(Account, account.id)
        assert fresh is not None and fresh.credential_generation == account.credential_generation == 0
        session.expunge(fresh)
    upstream.return_value = payload()
    await updater.build_background_usage_updater().force_refresh_result(fresh, ignore_refresh_disabled=True)
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["planCheckPending"]) == ("plus", True)
    evidence = await PlanDowngradeObservationStore().get(account.id)
    assert evidence is not None and evidence.observations == 1


@pytest.mark.parametrize("replace", [False, True])
async def test_first_free_enqueue_distinguishes_rotation_from_replacement(async_client, upstream, monkeypatch, replace):
    account = await seed()
    real_request = plan_checks.request_plan_check
    enc = TokenEncryptor()

    async def change_before_request(target, **kwargs):
        async with SessionLocal() as session:
            repo = AccountsRepository(session)
            if replace:
                # Even unchanged ciphertext is a new credential generation.
                assert await repo.replace_reauthorized(account.id, account) is not None
            else:
                assert await repo.rotate_tokens(
                    account.id,
                    enc.encrypt("rotated-access"),
                    enc.encrypt("rotated-refresh"),
                    enc.encrypt("rotated-id"),
                    utcnow(),
                    expected_refresh_token_encrypted=account.refresh_token_encrypted,
                )
        await real_request(target, **kwargs)

    monkeypatch.setattr(plan_checks, "request_plan_check", change_before_request)
    await updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert summary["planType"] == "plus"
    assert summary["planCheckPending"] is not replace
    async with SessionLocal() as session:
        saved = await session.get(Account, account.id)
        assert saved is not None and saved.credential_generation == (1 if replace else 0)
    if replace:
        assert await check_row() is None
        assert await PlanDowngradeObservationStore().get(account.id) is None
    else:
        await make_due()
        await PlanCheckScheduler().refresh_due()
        summary = (await async_client.get("/api/accounts/paid/summary")).json()
        assert (summary["planType"], summary["planCheckPending"]) == ("free", False)


async def test_deleted_account_id_reuse_fences_stale_plan_mutations(async_client, upstream):
    old = await seed()
    await updater.build_background_usage_updater().force_refresh_result(old, ignore_refresh_disabled=True)
    async with SessionLocal() as session:
        await session.execute(delete(Account).where(Account.id == old.id))
        await session.commit()
    fresh = await seed()
    assert fresh.codex_installation_id != old.codex_installation_id
    assert fresh.credential_generation == old.credential_generation == 0
    await updater.build_background_usage_updater().force_refresh_result(fresh, ignore_refresh_disabled=True)
    await plan_checks.request_plan_check(old, model="stale-model")
    check = await check_row()
    assert check is not None and check.rejected_model is None
    await PlanDowngradeObservationStore().clear(
        old.id, expected_credential_generation=0, expected_installation_id=old.codex_installation_id
    )
    evidence = await PlanDowngradeObservationStore().get(fresh.id)
    assert evidence is not None and evidence.observations == 1
    await make_due()
    await PlanCheckScheduler().refresh_due()
    summary = (await async_client.get("/api/accounts/paid/summary")).json()
    assert (summary["planType"], summary["planCheckPending"]) == ("free", False)


async def test_delayed_first_free_enqueue_preserves_later_confirmation(async_client, upstream, monkeypatch):
    account = await seed()
    await plan_checks.request_plan_check(account, model="gpt-test")
    # An earlier endpoint failure has already consumed one attempt.
    async with SessionLocal() as session:
        await session.execute(update(AccountPlanCheck).values(attempts=1))
        await session.commit()
    original = await check_row()
    real_enqueue = plan_checks.request_plan_check
    real_sync = updater.UsageUpdater._sync_identity_metadata
    first_observed, release_enqueue, enqueued = (asyncio.Event() for _ in range(3))

    async def delay_enqueue(account, **kwargs):
        first_observed.set()
        await release_enqueue.wait()
        await real_enqueue(account, **kwargs)
        enqueued.set()

    async def sync_after_enqueue(self, account, payload):
        if self._plan_check_generation is not None and payload.plan_type == "free":
            # The confirming sample has been consumed, but its guarded plan
            # write is still pending when the older enqueue resumes.
            release_enqueue.set()
            await enqueued.wait()
        return await real_sync(self, account, payload)

    monkeypatch.setattr(plan_checks, "request_plan_check", delay_enqueue)
    monkeypatch.setattr(updater.UsageUpdater, "_sync_identity_metadata", sync_after_enqueue)
    normal = asyncio.create_task(
        updater.build_background_usage_updater().force_refresh_result(account, ignore_refresh_disabled=True)
    )
    try:
        await asyncio.wait_for(first_observed.wait(), 5)
        await asyncio.wait_for(PlanCheckScheduler().refresh_due(), 5)
        await asyncio.wait_for(normal, 5)
        summary = (await async_client.get("/api/accounts/paid/summary")).json()
        confirmed = await check_row()
        assert confirmed is not None and original is not None
        assert confirmed.generation == original.generation and confirmed.attempts == 2 and confirmed.completed
        assert (summary["planType"], summary["status"], summary["planCheckPending"]) == ("free", "active", False)
        assert await PlanDowngradeObservationStore().get(account.id) is None
        await make_due()
        await PlanCheckScheduler().refresh_due()
        assert upstream.await_count == 2
    finally:
        release_enqueue.set()
        if not normal.done():
            normal.cancel()
        await asyncio.gather(normal, return_exceptions=True)


@pytest.mark.parametrize("existing_check", [False, True])
@pytest.mark.parametrize("clear_evidence", [False, True])
async def test_postgresql_delayed_enqueue_rechecks_consumed_evidence(db_setup, existing_check, clear_evidence):
    async with SessionLocal() as session:
        if session.get_bind().dialect.name != "postgresql":
            pytest.skip("PostgreSQL MVCC contention regression")
    account = await seed()
    if existing_check:
        await plan_checks.request_plan_check(account, model="gpt-test")
    old = await check_row()
    store = PlanDowngradeObservationStore()
    await store.observe(account.id, credential_fingerprint=credential_fingerprint(account), observed_plan_type="free")

    async def enqueue():
        async with SessionLocal() as session:
            return await PlanCheckRepository(session).request(account)

    async with SessionLocal() as confirmation:
        await lock_plan_check_account(confirmation, account.id)
        if clear_evidence:
            await confirmation.execute(delete(AccountPlanDowngradeObservation))
        else:
            await confirmation.execute(update(AccountPlanDowngradeObservation).values(observations=2))
        worker = asyncio.create_task(enqueue())
        try:
            async with asyncio.timeout(5):
                while True:
                    async with SessionLocal() as observer:
                        waiting = await observer.scalar(
                            text(
                                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                                "AND wait_event_type='Lock'"
                            )
                        )
                    if waiting:
                        break
                    await asyncio.sleep(0.01)
            await confirmation.commit()
            assert not await asyncio.wait_for(worker, 5)
        finally:
            await confirmation.rollback()
            if not worker.done():
                worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
    current = await check_row()
    if existing_check:
        assert current is not None and old is not None
        assert current.generation == old.generation
        assert current.next_attempt_at == old.next_attempt_at
    else:
        assert current is None


@pytest.mark.parametrize("operation", ["request", "observe", "clear", "ordinary_clear"])
async def test_postgresql_replacement_fences_already_waiting_priority_writes(db_setup, operation):
    async with SessionLocal() as session:
        if session.get_bind().dialect.name != "postgresql":
            pytest.skip("PostgreSQL MVCC contention regression")
    account = await seed()
    fingerprint = credential_fingerprint(account)
    await plan_checks.request_plan_check(account, model="gpt-test")
    check = await check_row()
    assert check is not None
    store = PlanDowngradeObservationStore()
    await store.observe(account.id, credential_fingerprint=fingerprint, observed_plan_type="free")

    async def old_work():
        if operation == "request":
            async with SessionLocal() as session:
                return await PlanCheckRepository(session).request(account, model="gpt-test")
        if operation == "clear":
            return await store.clear(account.id, plan_check_generation=check.generation)
        if operation == "ordinary_clear":
            return await store.clear(account.id, expected_credential_generation=account.credential_generation or 0)
        return await store.observe(
            account.id,
            credential_fingerprint=fingerprint,
            observed_plan_type="free",
            plan_check_generation=check.generation,
        )

    async with SessionLocal() as replacement:
        # The UPDATE holds the same parent-row lock as repository replacement;
        # cleanup is its real transactional discard seam, not an already
        # committed replacement staged before the stale query starts.
        await replacement.execute(
            update(Account)
            .where(Account.id == account.id)
            .values(
                refresh_token_encrypted=TokenEncryptor().encrypt("replacement"),
                credential_generation=Account.credential_generation + 1,
            )
        )
        await discard_plan_downgrade_observations(replacement, account.id)
        if operation == "ordinary_clear":
            replacement.add(
                AccountPlanDowngradeObservation(
                    account_id=account.id,
                    credential_fingerprint=fingerprint,
                    observations=1,
                    observed_plan_type="free",
                    first_observed_at=utcnow(),
                    last_observed_at=utcnow(),
                )
            )
            await replacement.flush()
        worker = asyncio.create_task(old_work())
        try:
            async with asyncio.timeout(5):
                while True:
                    async with SessionLocal() as observer:
                        waiting = await observer.scalar(
                            text(
                                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                                "AND wait_event_type='Lock'"
                            )
                        )
                    if waiting:
                        break
                    await asyncio.sleep(0.01)
            await replacement.commit()
            result = await worker
        finally:
            await replacement.rollback()
            if not worker.done():
                worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
    assert result is None if operation in {"clear", "ordinary_clear"} else not result
    assert await check_row() is None
    if operation == "ordinary_clear":
        evidence = await store.get(account.id)
        assert evidence is not None and evidence.observations == 1
        return
    assert await store.get(account.id) is None
    async with SessionLocal() as session:
        repaired = await session.get(Account, account.id)
        assert repaired is not None
        assert not await PlanCheckRepository(session).matching_ids([repaired], model="gpt-test")
    # One fresh Free observation must remain one, never inherit the old sample.
    assert await store.observe(account.id, credential_fingerprint=fingerprint, observed_plan_type="free") == 1


@pytest.mark.parametrize("timeout", [False, True])
async def test_priority_cancellation_drains_real_oauth_persistence(db_setup, upstream, monkeypatch, timeout):
    account = await seed()
    await plan_checks.request_plan_check(account, model="gpt-test")
    upstream.side_effect = UsageFetchError(401, "revoked access", code="token_revoked")
    monkeypatch.setattr(plan_check_scheduler, "refresh_subscription", AsyncMock())
    monkeypatch.setattr(auth_manager, "resolve_upstream_route", AsyncMock(return_value=None))
    started, release_exchange, writing, release_write = (asyncio.Event() for _ in range(4))
    real_rotate = BackgroundAccountsRepository.rotate_tokens

    async def exchange(*args, **kwargs):
        started.set()
        await release_exchange.wait()
        return TokenRefreshResult("rotated-access", "rotated-refresh", "rotated-id", None, "plus", None)

    async def persist(self, *args, **kwargs):
        writing.set()
        await release_write.wait()
        return await real_rotate(self, *args, **kwargs)

    monkeypatch.setattr(auth_manager, "refresh_access_token", exchange)
    monkeypatch.setattr(BackgroundAccountsRepository, "rotate_tokens", persist)
    scheduler = PlanCheckScheduler()
    timeout_scope = asyncio.timeout(None)

    async def timed_check():
        async with timeout_scope:
            await scheduler.refresh_due()

    if timeout:
        task = asyncio.create_task(timed_check())
    else:
        await scheduler.start()
        task = scheduler._task
        assert task is not None
    stop = None
    joined = None
    try:
        await asyncio.wait_for(started.wait(), 5)
        manager = auth_manager.AuthManager(BackgroundAccountsRepository())
        joined = asyncio.create_task(manager.ensure_fresh(account, force=True))
        await asyncio.sleep(0)
        if timeout:
            timeout_scope.reschedule(asyncio.get_running_loop().time())
            stop = task
        else:
            stop = asyncio.create_task(scheduler.stop())
        await asyncio.sleep(0)
        release_exchange.set()
        await asyncio.wait_for(writing.wait(), 5)
        assert not stop.done(), "stop/timeout returned before rotated credentials were saved"
        release_write.set()
        if timeout:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(stop, 5)
        else:
            await asyncio.wait_for(stop, 5)
        assert (await joined).status == AccountStatus.ACTIVE
        async with SessionLocal() as session:
            saved = await session.get(Account, account.id)
            assert saved is not None
            assert TokenEncryptor().decrypt(saved.refresh_token_encrypted) == "rotated-refresh"
        assert not any(not active.done() for active in auth_manager._REFRESH_SINGLEFLIGHT._inflight.values())
        assert upstream.await_count == 1  # no usage retry after cancellation
    finally:
        release_exchange.set()
        release_write.set()
        await scheduler.stop()
        if not task.done():
            task.cancel()
        await asyncio.gather(
            *(pending for pending in (task, stop, joined) if pending is not None), return_exceptions=True
        )
