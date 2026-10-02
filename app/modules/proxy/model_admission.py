from __future__ import annotations

import logging

from app.core.clients.proxy import ProxyResponseError
from app.core.errors import openai_error
from app.db.models import Account
from app.modules.usage import plan_checks

logger = logging.getLogger(__name__)


async def rejected_model_account_ids(accounts: list[Account], model: str | None) -> set[str]:
    try:
        return await plan_checks.rejected_model_account_ids(accounts, model)
    except Exception as exc:
        # This is a local pre-dispatch failure, not evidence about upstream
        # health or transport integrity, including unwrapped driver connection
        # failures. Cancellation remains uncaught. Keep driver details private.
        logger.warning("Model admission lookup failed: %s", type(exc).__name__)
        raise ProxyResponseError(
            503,
            openai_error("upstream_unavailable", "Account model availability could not be checked; retry later."),
        ) from exc
