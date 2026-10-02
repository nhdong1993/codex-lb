"""Shared, short-lived priority checks. Network work belongs to the scheduler."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plan_types import ACCOUNT_PLAN_TYPES
from app.core.utils.time import utcnow
from app.db.models import Account, AccountPlanCheck, AccountPlanDowngradeObservation, AccountStatus
from app.db.session import get_background_session, sqlite_writer_section
from app.modules.usage.plan_check_lock import lock_plan_check_account
from app.modules.usage.plan_downgrade_observations import credential_fingerprint

CHECK_WINDOW = timedelta(minutes=2)
CHECK_RETRY_DELAY = timedelta(seconds=15)
CHECK_LEASE = timedelta(seconds=60)
MAX_CHECK_ATTEMPTS = 3


def eligible_for_plan_check(account: Account) -> bool:
    return (
        account.plan_type in ACCOUNT_PLAN_TYPES
        and bool(account.chatgpt_account_id)
        and account.delete_requested_at is None
        and account.status not in {AccountStatus.PAUSED, AccountStatus.DEACTIVATED, AccountStatus.REAUTH_REQUIRED}
    )


class PlanCheckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def request(self, account: Account, *, model: str | None = None) -> bool:
        if not eligible_for_plan_check(account):
            return False
        now = utcnow()
        fingerprint = credential_fingerprint(account)
        pending_free = (
            select(AccountPlanDowngradeObservation.account_id)
            .where(
                AccountPlanDowngradeObservation.account_id == account.id,
                AccountPlanDowngradeObservation.credential_fingerprint == fingerprint,
                AccountPlanDowngradeObservation.observed_plan_type == "free",
                AccountPlanDowngradeObservation.observations == 1,
            )
            .exists()
        )
        # The INSERT source guard prevents a delayed request from re-enqueuing
        # work after import/reauth replaced the credentials and cleared the row.
        source = select(
            Account.id,
            literal(uuid4().hex),
            literal(fingerprint),
            literal(now),
            literal(now if model else now + CHECK_RETRY_DELAY),
            literal(0),
            literal(False),
            literal(model),
        ).where(
            Account.id == account.id,
            Account.credential_generation == (account.credential_generation or 0),
            Account.codex_installation_id == account.codex_installation_id,
            Account.plan_type == account.plan_type,
            Account.delete_requested_at.is_(None),
            Account.status.notin_([AccountStatus.PAUSED, AccountStatus.DEACTIVATED, AccountStatus.REAUTH_REQUIRED]),
        )
        if model is None:
            source = source.where(pending_free)
        insert = pg_insert if self.session.bind.dialect.name == "postgresql" else sqlite_insert
        stmt = insert(AccountPlanCheck).from_select(
            [
                "account_id",
                "generation",
                "credential_fingerprint",
                "requested_at",
                "next_attempt_at",
                "attempts",
                "completed",
                "rejected_model",
            ],
            source,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AccountPlanCheck.account_id],
            set_={
                name: stmt.excluded[name]
                for name in (
                    "generation",
                    "credential_fingerprint",
                    "requested_at",
                    "next_attempt_at",
                    "attempts",
                    "completed",
                    "rejected_model",
                )
            },
            where=or_(
                AccountPlanCheck.requested_at <= now - CHECK_WINDOW,
                AccountPlanCheck.credential_fingerprint != fingerprint,
            ),
        ).returning(AccountPlanCheck.account_id)
        async with sqlite_writer_section():
            await lock_plan_check_account(self.session, account.id)
            result = await self.session.scalar(stmt)
            if model and result is None:
                # Keep the original budget/deadline when another model rejects.
                await self.session.execute(
                    update(AccountPlanCheck)
                    .where(
                        AccountPlanCheck.account_id == account.id,
                        AccountPlanCheck.credential_fingerprint == fingerprint,
                        select(Account.id)
                        .where(
                            Account.id == account.id,
                            Account.credential_generation == (account.credential_generation or 0),
                            Account.codex_installation_id == account.codex_installation_id,
                        )
                        .exists(),
                    )
                    .values(rejected_model=model)
                )
            elif model is None and result is None:
                # A separate refresh can observe Free after a paid sample but
                # before its check finishes. Fence that in-flight completion
                # as well as completed work, preserving the original budget.
                # Recheck evidence under the account lock: a delayed first
                # observer must not fence a worker that already confirmed Free.
                result = await self.session.scalar(
                    update(AccountPlanCheck)
                    .where(
                        AccountPlanCheck.account_id == account.id,
                        AccountPlanCheck.credential_fingerprint == fingerprint,
                        AccountPlanCheck.attempts < MAX_CHECK_ATTEMPTS,
                        AccountPlanCheck.requested_at > now - CHECK_WINDOW,
                        pending_free,
                        select(Account.id)
                        .where(
                            Account.id == account.id,
                            Account.credential_generation == (account.credential_generation or 0),
                            Account.codex_installation_id == account.codex_installation_id,
                            Account.plan_type == account.plan_type,
                            Account.delete_requested_at.is_(None),
                            Account.status.notin_(
                                [AccountStatus.PAUSED, AccountStatus.DEACTIVATED, AccountStatus.REAUTH_REQUIRED]
                            ),
                        )
                        .exists(),
                    )
                    .values(completed=False, generation=uuid4().hex, next_attempt_at=now + CHECK_RETRY_DELAY)
                    .returning(AccountPlanCheck.account_id)
                )
            await self.session.commit()
        return result is not None

    async def claim_due(self, limit: int = 3) -> list[AccountPlanCheck]:
        now = utcnow()
        due = (
            AccountPlanCheck.completed.is_(False),
            AccountPlanCheck.attempts < MAX_CHECK_ATTEMPTS,
            AccountPlanCheck.next_attempt_at <= now,
            AccountPlanCheck.requested_at > now - CHECK_WINDOW,
        )
        async with sqlite_writer_section():
            await self.session.execute(
                delete(AccountPlanCheck).where(AccountPlanCheck.requested_at <= now - CHECK_WINDOW)
            )
            ids = list(
                await self.session.scalars(
                    select(AccountPlanCheck.account_id)
                    .where(*due)
                    .order_by(AccountPlanCheck.next_attempt_at)
                    .limit(limit)
                )
            )
            rows = (
                list(
                    await self.session.scalars(
                        update(AccountPlanCheck)
                        .where(AccountPlanCheck.account_id.in_(ids), *due)
                        .values(next_attempt_at=now + CHECK_LEASE, attempts=AccountPlanCheck.attempts + 1)
                        .returning(AccountPlanCheck)
                    )
                )
                if ids
                else []
            )
            await self.session.commit()
        for row in rows:
            self.session.expunge(row)
        return rows

    async def finish(self, claim: AccountPlanCheck, *, complete: bool) -> None:
        async with sqlite_writer_section():
            await self.session.execute(
                update(AccountPlanCheck)
                .where(
                    AccountPlanCheck.account_id == claim.account_id,
                    AccountPlanCheck.generation == claim.generation,
                    AccountPlanCheck.attempts == claim.attempts,
                )
                .values(
                    completed=complete or claim.attempts >= MAX_CHECK_ATTEMPTS,
                    next_attempt_at=utcnow() + CHECK_RETRY_DELAY,
                )
            )
            await self.session.commit()

    async def current(self, claim: AccountPlanCheck) -> bool:
        return (
            await self.session.scalar(
                select(AccountPlanCheck.account_id).where(
                    AccountPlanCheck.account_id == claim.account_id,
                    AccountPlanCheck.generation == claim.generation,
                    AccountPlanCheck.attempts == claim.attempts,
                )
            )
            is not None
        )

    async def matching_ids(self, accounts: list[Account], *, model: str | None = None) -> set[str]:
        if not accounts:
            return set()
        rows = await self.session.scalars(
            select(AccountPlanCheck).where(
                AccountPlanCheck.account_id.in_([account.id for account in accounts]),
                AccountPlanCheck.requested_at > utcnow() - CHECK_WINDOW,
                AccountPlanCheck.rejected_model == model
                if model is not None
                else AccountPlanCheck.completed.is_(False),
            )
        )
        accounts_by_id = {account.id: account for account in accounts}
        return {
            row.account_id
            for row in rows
            if credential_fingerprint(accounts_by_id[row.account_id]) == row.credential_fingerprint
        }


async def request_plan_check(account: Account, *, model: str | None = None) -> None:
    async with get_background_session() as session:
        await PlanCheckRepository(session).request(account, model=model)


async def plan_check_is_current(account: Account, generation: str) -> bool:
    async with get_background_session() as session:
        return (
            await session.scalar(
                select(AccountPlanCheck.account_id)
                .join(Account)
                .where(
                    AccountPlanCheck.account_id == account.id,
                    AccountPlanCheck.generation == generation,
                    Account.credential_generation == (account.credential_generation or 0),
                    Account.codex_installation_id == account.codex_installation_id,
                )
            )
            is not None
        )


async def pending_plan_check_ids(accounts: list[Account]) -> set[str]:
    eligible = [account for account in accounts if eligible_for_plan_check(account) and account.plan_type != "free"]
    async with get_background_session() as session:
        return await PlanCheckRepository(session).matching_ids(eligible)


async def rejected_model_account_ids(accounts: list[Account], model: str | None) -> set[str]:
    if not model or not accounts:
        return set()
    async with get_background_session() as session:
        return await PlanCheckRepository(session).matching_ids(accounts, model=model)
