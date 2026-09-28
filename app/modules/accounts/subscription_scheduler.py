from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field

from app.core.scheduling.leader_election_handle import get_leader_election as _get_leader_election
from app.core.utils.time import utcnow
from app.db.session import get_background_session
from app.modules.accounts.subscription_repository import SubscriptionRepository
from app.modules.accounts.subscription_service import SUBSCRIPTION_REFRESH_INTERVAL, refresh_subscription

logger = logging.getLogger(__name__)
_WORKERS = 3


@dataclass(slots=True)
class SubscriptionRefreshScheduler:
    interval_seconds: float = 60
    _task: asyncio.Task[None] | None = None
    _stop: asyncio.Event = field(default_factory=asyncio.Event)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await _get_leader_election().run_if_leader(self.refresh_due)
            except Exception as exc:
                logger.warning("Subscription refresh pass failed error_type=%s", type(exc).__name__)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

    async def refresh_due(self) -> None:
        async with get_background_session() as session:
            account_ids = iter(await SubscriptionRepository(session).due_ids(utcnow() - SUBSCRIPTION_REFRESH_INTERVAL))

        async def worker() -> None:
            for account_id in account_ids:
                try:
                    await refresh_subscription(account_id)
                except Exception as exc:
                    # Never log upstream exception strings: transport errors
                    # can include proxy credentials or bearer headers.
                    logger.warning(
                        "Subscription refresh failed account_id=%s error_type=%s", account_id, type(exc).__name__
                    )

        async with asyncio.TaskGroup() as group:
            for _ in range(_WORKERS):
                group.create_task(worker())
