from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.clients.proxy import ProxyResponseError
from app.core.config.settings_cache import get_settings_cache
from app.core.errors import openai_error
from app.core.model_plan_policy import ModelPlanPolicies, model_plan_allowed, parse_model_plan_policies
from app.db.models import Account, DashboardSettings
from app.db.session import get_background_session
from app.modules.usage import plan_checks

logger = logging.getLogger(__name__)


class NativeModelAdmissionError(ProxyResponseError):
    """Unsent native HTTP work: never an upstream retry or health signal."""


async def ensure_native_dispatch_allowed(account: Account, model: str | None, api_key_id: str | None = None) -> None:
    """Recheck the effective Plan policy and persisted plan after every admission wait.

    Unconfigured models keep their existing dispatch path: no extra lookup, and
    plan-check rejections stay selection-time evidence that fails over normally.
    """
    try:
        _, policies = await routing_policy_snapshot()
        rejected = await _plan_policy_rejected_ids(policies, [account], model, api_key_id)
    except ProxyResponseError as exc:
        raise NativeModelAdmissionError(exc.status_code, exc.payload, failure_phase="admission") from exc
    if rejected:
        raise NativeModelAdmissionError(
            503,
            openai_error("upstream_unavailable", "Account is unavailable for this model; retry later."),
            failure_phase="admission",
        )


async def rejected_model_account_ids(
    accounts: list[Account], model: str | None, api_key_id: str | None = None
) -> set[str]:
    try:
        _, policies = await routing_policy_snapshot()
        rejected = await plan_checks.rejected_model_account_ids(accounts, model)
    except Exception as exc:
        raise _lookup_failure(exc) from exc
    return rejected | await _plan_policy_rejected_ids(policies, accounts, model, api_key_id)


async def policy_rejected_account_ids(accounts: list[Account], model: str | None, api_key_id: str | None) -> set[str]:
    """Operator Plan policy only (no plan-check evidence): the recheck for bridge resends after a wait."""
    _, policies = await routing_policy_snapshot()
    return await _plan_policy_rejected_ids(policies, accounts, model, api_key_id)


async def routing_policy_snapshot() -> tuple[DashboardSettings, ModelPlanPolicies]:
    try:
        settings = await get_settings_cache().get()
        return settings, parse_model_plan_policies(settings.model_plan_routing_policies_json)
    except Exception as exc:
        logger.warning("Routing policy lookup failed: %s", type(exc).__name__)
        raise ProxyResponseError(
            503, openai_error("upstream_unavailable", "Account routing policy could not be checked; retry later.")
        ) from exc


async def _plan_policy_rejected_ids(
    policies: ModelPlanPolicies, accounts: list[Account], model: str | None, api_key_id: str | None = None
) -> set[str]:
    if model not in policies or not accounts:
        return set()
    try:
        # Sockets hold detached account snapshots. Read current persisted plans
        # in our own session, outside the bridge registry lock; deleted owners
        # also fail closed. No entitlement-equivalence widening here.
        async with get_background_session() as session:
            rows = await session.execute(
                select(Account.id, Account.plan_type, Account.reserved_api_key_id).where(
                    Account.id.in_([a.id for a in accounts])
                )
            )
            current = {account_id: (plan, owner) for account_id, plan, owner in rows.all()}
    except Exception as exc:
        raise _lookup_failure(exc) from exc
    return {a.id for a in accounts if not _plan_admitted(policies, model, current.get(a.id), api_key_id)}


def _plan_admitted(
    policies: ModelPlanPolicies, model: str | None, row: tuple[str, str | None] | None, api_key_id: str | None
) -> bool:
    if row is None:
        return False
    plan, owner = row
    # The requesting key's own reserved account is exempt; ownership comes from the same row read.
    return model_plan_allowed(policies, model, plan) or (api_key_id is not None and owner == api_key_id)


def _lookup_failure(exc: Exception) -> ProxyResponseError:
    # This is a local pre-dispatch failure, not evidence about upstream
    # health or transport integrity, including unwrapped driver connection
    # failures. Cancellation remains uncaught. Keep driver details private.
    logger.warning("Model admission lookup failed: %s", type(exc).__name__)
    return ProxyResponseError(
        503,
        openai_error("upstream_unavailable", "Account model availability could not be checked; retry later."),
    )
