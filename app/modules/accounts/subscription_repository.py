from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.plan_types import ACCOUNT_PLAN_TYPES
from app.core.utils.time import to_utc_naive
from app.db.models import Account, AccountStatus


def subscription_fingerprint(account: Account, *, access_token_encrypted: bytes | None = None) -> str:
    identity = json.dumps([account.id, account.chatgpt_account_id, account.plan_type]).encode()
    credential = account.access_token_encrypted if access_token_encrypted is None else access_token_encrypted
    return hashlib.sha256(identity + b"\0" + credential).hexdigest()


def _eligible() -> ColumnElement[bool]:
    return (
        Account.plan_type.in_(ACCOUNT_PLAN_TYPES - {"free"})
        & Account.status.notin_([AccountStatus.DEACTIVATED, AccountStatus.REAUTH_REQUIRED])
        & Account.delete_requested_at.is_(None)
        & Account.chatgpt_account_id.is_not(None)
        & (Account.chatgpt_account_id != "")
    )


def _due(cutoff: datetime) -> ColumnElement[bool]:
    return or_(Account.subscription_attempted_at.is_(None), Account.subscription_attempted_at <= cutoff)


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def due_ids(self, cutoff: datetime) -> list[str]:
        rows = await self._session.scalars(
            select(Account.id)
            .where(_eligible(), _due(cutoff))
            .order_by(Account.subscription_attempted_at.asc().nullsfirst(), Account.id)
        )
        return list(rows)

    async def claim(self, account_id: str, *, attempted_at: datetime, cutoff: datetime) -> Account | None:
        # One shared attempt clock prevents followers/restarts from hammering a
        # failing account. No credentials or subscription result are mutated.
        result = await self._session.scalars(
            update(Account)
            .where(Account.id == account_id, _eligible(), _due(cutoff))
            .values(subscription_attempted_at=attempted_at)
            .returning(Account)
        )
        account = result.one_or_none()
        await self._session.commit()
        if account is not None:
            self._session.expunge(account)
        return account

    async def save(self, account: Account, *, active_until: datetime | None, checked_at: datetime) -> bool:
        saved = await self._session.scalar(
            update(Account)
            .where(
                Account.id == account.id,
                _eligible(),
                Account.chatgpt_account_id == account.chatgpt_account_id,
                Account.plan_type == account.plan_type,
                Account.access_token_encrypted == account.access_token_encrypted,
                Account.subscription_attempted_at == account.subscription_attempted_at,
            )
            .values(
                subscription_active_until=to_utc_naive(active_until) if active_until else None,
                subscription_checked_at=to_utc_naive(checked_at),
                subscription_fingerprint=subscription_fingerprint(account),
            )
            .returning(Account.id)
        )
        await self._session.commit()
        return saved is not None
