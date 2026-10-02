from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account


async def lock_plan_check_account(session: AsyncSession, account_id: str) -> None:
    """Serialize priority writes with replacement before reading their source.

    PostgreSQL INSERT SELECT can retain a pre-replacement snapshot while
    waiting on a child-row conflict. Lock the parent first, matching the
    account repository's NO KEY UPDATE lock and account-before-child order.
    SQLite's write statements already serialize under its single writer.
    """
    if session.get_bind().dialect.name == "postgresql":
        await session.scalar(select(Account.id).where(Account.id == account_id).with_for_update(key_share=True))
