from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field

from app.core.scheduling.leader_election_handle import get_leader_election
from app.db.models import AccountPlanCheck
from app.db.session import get_background_session
from app.modules.accounts.subscription_service import refresh_subscription
from app.modules.usage.plan_checks import PlanCheckRepository, eligible_for_plan_check
from app.modules.usage.plan_downgrade_observations import credential_fingerprint
from app.modules.usage.updater import UsageUpdater

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PlanCheckScheduler:
    _task: asyncio.Task[None] | None = None
    _stop: asyncio.Event = field(default_factory=asyncio.Event)

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await get_leader_election().run_if_leader(self.refresh_due)
            except Exception as exc:
                logger.warning("Priority plan check pass failed error_type=%s", type(exc).__name__)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass

    async def refresh_due(self) -> None:
        async with get_background_session() as session:
            claims = await PlanCheckRepository(session).claim_due()
        async with asyncio.TaskGroup() as group:
            for claim in claims:
                group.create_task(self._check(claim))

    async def _check(self, claim: AccountPlanCheck) -> None:
        complete = False
        try:
            async with get_background_session() as session:
                if not await PlanCheckRepository(session).current(claim):
                    return
            loaded = await UsageUpdater._load_owned_session_updater(claim.account_id)
            if loaded is None:
                complete = True
                return
            updater, account = loaded
            if not eligible_for_plan_check(account) or credential_fingerprint(account) != claim.credential_fingerprint:
                complete = True
                return
            # Independent endpoints: a challenged subscriptions response must
            # not prevent the usage endpoint from confirming the actual plan.
            try:
                async with asyncio.timeout(22):
                    await refresh_subscription(account.id, manual=True)
            except Exception as exc:
                logger.info(
                    "Priority subscription check failed account_id=%s error_type=%s", account.id, type(exc).__name__
                )
            updater._plan_check_generation = claim.generation
            async with asyncio.timeout(25):
                # Priority usage cancels its fetch and drains any shared OAuth
                # exchange/persistence before propagating cancellation.
                result = await updater._refresh_account(account, usage_account_id=account.chatgpt_account_id)
            complete = result.fetch_succeeded
        except Exception as exc:
            logger.warning(
                "Priority plan check failed account_id=%s error_type=%s", claim.account_id, type(exc).__name__
            )
        finally:
            # Cancellation deliberately leaves the bounded claim to expire.
            task = asyncio.current_task()
            if task is not None and not task.cancelling():
                try:
                    async with get_background_session() as session:
                        await PlanCheckRepository(session).finish(claim, complete=complete)
                except Exception as exc:
                    logger.warning("Priority check completion failed error_type=%s", type(exc).__name__)
