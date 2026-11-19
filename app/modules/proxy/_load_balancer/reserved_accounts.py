"""Keep accounts reserved for another API key out of account selection."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import replace
from typing import Any, TypeVar

from app.modules.proxy._load_balancer.sticky_selection import SelectionInputsProtocol

SelectionInputsT = TypeVar("SelectionInputsT", bound=SelectionInputsProtocol)


def drop_foreign_reserved(inputs: SelectionInputsT, api_key_id: str | None) -> SelectionInputsT:
    """Drop accounts reserved for a key other than ``api_key_id`` (every reserved account when keyless).

    ``runtime_accounts`` keeps the full list: runtime-state pruning and the
    "owner deleted" vs "owner outside policy" decision both read it.
    """
    owners = inputs.continuity_owner_candidates
    foreign = {
        account.id
        # runtime_accounts covers ids present only in the sticky authority (e.g. model-ineligible accounts).
        for account in [*inputs.accounts, *(owners or ()), *(inputs.runtime_accounts or ())]
        if account.reserved_api_key_id is not None and account.reserved_api_key_id != api_key_id
    }
    if not foreign:
        return inputs
    authority = inputs.sticky_mutation_authority_account_ids
    return replace(
        inputs,
        accounts=[account for account in inputs.accounts if account.id not in foreign],
        continuity_owner_candidates=None if owners is None else [a for a in owners if a.id not in foreign],
        sticky_mutation_authority_account_ids=None if authority is None else authority - foreign,
        runtime_accounts=inputs.accounts if inputs.runtime_accounts is None else inputs.runtime_accounts,
    )


async def load_inputs_for_key(
    load: Callable[..., Awaitable[SelectionInputsT]],
    api_key_id: str | None,
    *,
    owner_overrides: Mapping[str, Any] | None = None,
    **load_kwargs: Any,
) -> SelectionInputsT:
    """Load selection inputs as ``api_key_id`` sees them.

    Other keys and keyless requests get the shared load unchanged. A key that owns a reserved
    account reloads with the model Plan exemption; that load decides ownership from its own rows,
    so a reservation released in between does not stay exempt. ``owner_overrides`` narrows only
    that reload, for callers whose shared load is deliberately wider than their selector.
    """
    inputs = await load(**load_kwargs)
    # Without a model there is no Plan filter to exempt from.
    if api_key_id is not None and load_kwargs.get("model") and _owns_reserved(inputs, api_key_id):
        owner_inputs = await load(**{**load_kwargs, **(owner_overrides or {})}, plan_exempt_api_key_id=api_key_id)
        if owner_overrides is None or _owns_reserved(owner_inputs, api_key_id):
            inputs = owner_inputs
        else:
            # Released between the loads: the owner-only narrowing no longer applies.
            inputs = await load(**load_kwargs)
    return drop_foreign_reserved(inputs, api_key_id)


def _owns_reserved(inputs: SelectionInputsProtocol, api_key_id: str) -> bool:
    accounts = inputs.accounts if inputs.runtime_accounts is None else inputs.runtime_accounts
    return any(account.reserved_api_key_id == api_key_id for account in accounts)
