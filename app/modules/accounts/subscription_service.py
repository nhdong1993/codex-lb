from __future__ import annotations

from datetime import timedelta

from app.core.clients.subscriptions import fetch_subscription_term
from app.core.crypto import TokenEncryptor
from app.core.upstream_proxy import resolve_upstream_route
from app.core.utils.time import utcnow
from app.db.session import get_background_session
from app.modules.accounts.subscription_repository import SubscriptionRepository

SUBSCRIPTION_REFRESH_INTERVAL = timedelta(days=1)


async def refresh_subscription(account_id: str, *, manual: bool = False) -> bool:
    now = utcnow()
    async with get_background_session() as session:
        account = await SubscriptionRepository(session).claim(
            account_id,
            attempted_at=now,
            cutoff=now - (timedelta(seconds=30) if manual else SUBSCRIPTION_REFRESH_INTERVAL),
        )
    if account is None or not account.chatgpt_account_id:
        return False
    encryptor = TokenEncryptor()
    async with get_background_session() as session:
        route = await resolve_upstream_route(
            session, account_id=account.id, operation="subscription_refresh", encryptor=encryptor
        )
    active_until = await fetch_subscription_term(
        access_token=encryptor.decrypt(account.access_token_encrypted),
        account_id=account.chatgpt_account_id,
        plan_type=account.plan_type,
        route=route,
        allow_direct_egress=route is None,
    )
    async with get_background_session() as session:
        return await SubscriptionRepository(session).save(account, active_until=active_until, checked_at=utcnow())
