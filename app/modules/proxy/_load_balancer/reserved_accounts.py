"""Keep accounts reserved for another API key out of account selection."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
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
    exempt: bool = True,
    **load_kwargs: Any,
) -> SelectionInputsT:
    """Load selection inputs as ``api_key_id`` sees them.

    Other keys and keyless requests get the shared load unchanged. A key that owns a reserved
    account reloads with the model Plan policy exemption; the loader decides from the policy
    snapshot it filters with and from its own rows, so neither an unmapped model nor a
    reservation released in between gains an exemption.
    """
    inputs = await load(**load_kwargs)
    accounts = inputs.accounts if inputs.runtime_accounts is None else inputs.runtime_accounts
    owns_reserved = any(account.reserved_api_key_id == api_key_id for account in accounts)
    if exempt and api_key_id is not None and load_kwargs.get("model") and owns_reserved:
        # shortcut: an unmapped model reloads under the baseline cache key, a cache hit unless the
        # entry expired or the key changed in between; carry the mapping on the inputs if that costs too much.
        inputs = await load(**load_kwargs, plan_exempt_api_key_id=api_key_id)
    return drop_foreign_reserved(inputs, api_key_id)
