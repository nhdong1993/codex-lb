"""Keep accounts reserved for another API key out of account selection."""

from __future__ import annotations

from dataclasses import replace
from typing import TypeVar

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
