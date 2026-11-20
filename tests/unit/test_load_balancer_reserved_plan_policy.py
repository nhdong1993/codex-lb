"""A key's reserved accounts are exempt from the operator subscription model Plan restriction."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any, cast

import pytest

import app.modules.proxy.load_balancer as load_balancer_module
from app.db.models import Account
from app.modules.proxy import model_admission
from app.modules.proxy.account_cache import AccountSelectionCache
from app.modules.proxy.load_balancer import LoadBalancer
from tests.unit.test_load_balancer_contract import _account, _balancer, _usage_row

pytestmark = pytest.mark.unit

MODEL = "gpt-x"
UNMAPPED = "gpt-y"
_ROUNDS = 8
Outcome = tuple[str | None, str | None, str | None]


class _Policies:
    """Stateful ``routing_policy_snapshot`` stub; ``sequence`` lets a test change the mapping between reads."""

    def __init__(self, *sequence: dict[str, list[str]]) -> None:
        self._sequence = list(sequence) or [{MODEL: ["free"]}]
        self.reads = 0

    async def __call__(self) -> tuple[Any, dict[str, list[str]]]:
        policies = self._sequence[min(self.reads, len(self._sequence) - 1)]
        self.reads += 1
        return SimpleNamespace(additional_quota_routing_policies_json="{}"), policies


@pytest.fixture(autouse=True)
def _isolate_runtime_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(load_balancer_module, "get_settings", lambda: SimpleNamespace(circuit_breaker_enabled=False))
    monkeypatch.setattr(load_balancer_module, "set_normal", lambda: None)
    monkeypatch.setattr(load_balancer_module, "set_degraded", lambda _reason: None)

    async def _no_admission_rejections(*_args: object, **_kwargs: object) -> set[str]:
        return set()

    monkeypatch.setattr(model_admission, "rejected_model_account_ids", _no_admission_rejections)


def _policies(monkeypatch: pytest.MonkeyPatch, *sequence: dict[str, list[str]]) -> _Policies:
    stub = _Policies(*sequence)
    monkeypatch.setattr(model_admission, "routing_policy_snapshot", stub)
    return stub


def _acct(account_id: str, plan: str, *, reserved_for: str | None = None) -> Account:
    account = _account(account_id)
    account.plan_type = plan
    account.reserved_api_key_id = reserved_for
    return account


def _pool(accounts: list[Account], *, cache: AccountSelectionCache | None = None) -> tuple[LoadBalancer, Any]:
    primary = {a.id: _usage_row(i, a.id, window="primary", used_percent=10.0) for i, a in enumerate(accounts, 1)}
    balancer, accounts_repo, _, _ = _balancer(accounts, cache or AccountSelectionCache(ttl_seconds=0), primary=primary)
    return balancer, accounts_repo


async def _picks(balancer: LoadBalancer, api_key_id: str | None, *, model: str = MODEL, **kwargs: Any) -> set:
    picked: set[str | None] = set()
    for _ in range(_ROUNDS):
        selection = await balancer.select_account(model=model, api_key_id=api_key_id, **kwargs)
        picked.add(selection.account.id if selection.account else None)
    return picked


async def _outcome(balancer: LoadBalancer, api_key_id: str | None) -> Outcome:
    selection = await balancer.select_account(model=MODEL, api_key_id=api_key_id)
    return (selection.account.id if selection.account else None, selection.error_code, selection.error_message)


def _shared_pool() -> list[Account]:
    return [_acct("r", "plus", reserved_for="K"), _acct("s", "free"), _acct("p", "plus")]


@pytest.mark.asyncio
async def test_owner_key_uses_its_reserved_account_outside_the_plan_restriction(monkeypatch) -> None:
    _policies(monkeypatch)
    balancer, _ = _pool(_shared_pool())

    assert await _picks(balancer, "K") == {"r"}


@pytest.mark.asyncio
async def test_unusable_reserved_account_falls_back_to_the_restricted_pool(monkeypatch) -> None:
    _policies(monkeypatch)
    balancer, _ = _pool(_shared_pool())
    balancer._runtime["r"] = load_balancer_module.RuntimeState(cooldown_until=time.time() + 600)

    assert await _picks(balancer, "K") == {"s"}


@pytest.mark.asyncio
async def test_other_keys_and_keyless_keep_the_restricted_result(monkeypatch) -> None:
    _policies(monkeypatch)
    balancer, _ = _pool(_shared_pool())
    for api_key_id in ("J", None):
        assert await _picks(balancer, api_key_id) == {"s"}

    only_paid, _ = _pool([_acct("r", "plus", reserved_for="K"), _acct("p", "plus")])
    # The baseline (HEAD) outcome for a restricted pool with no Free account.
    head = (
        None,
        None,
        "No available accounts. Service is operating in degraded mode: upstream capacity is currently unavailable",
    )
    for api_key_id in ("J", None):
        assert await _outcome(only_paid, api_key_id) == head
    assert await _picks(only_paid, "K") == {"r"}


@pytest.mark.asyncio
async def test_plan_exempt_false_keeps_the_restriction_for_the_owner(monkeypatch) -> None:
    _policies(monkeypatch)
    balancer, _ = _pool(_shared_pool())

    assert await _picks(balancer, "K", plan_exempt=False) == {"s"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("new_owner", "expected"), [("K", {"r"}), (None, {"s"}), ("J", {"s"})])
async def test_exemption_follows_the_reservation_read_by_the_owner_load(monkeypatch, new_owner, expected) -> None:
    _policies(monkeypatch)
    accounts = _shared_pool()
    balancer, accounts_repo = _pool(accounts)
    original = accounts_repo.list_accounts

    async def list_accounts() -> list[Account]:
        if accounts_repo.list_calls >= 1:
            accounts[0].reserved_api_key_id = new_owner
        return await original()

    accounts_repo.list_accounts = list_accounts
    selection = await balancer.select_account(model=MODEL, api_key_id="K")

    assert {selection.account.id if selection.account else None} == expected


@pytest.mark.asyncio
async def test_only_the_owner_key_adds_a_cache_entry_for_a_mapped_model(monkeypatch) -> None:
    _policies(monkeypatch)
    cache = AccountSelectionCache(ttl_seconds=60)
    balancer, _ = _pool(_shared_pool(), cache=cache)

    await balancer.select_account(model=MODEL, api_key_id="J")
    await balancer.select_account(model=MODEL, api_key_id=None)
    baseline = len(cache._cache)
    await balancer.select_account(model=MODEL, api_key_id="K")
    await balancer.select_account(model=MODEL, api_key_id="K")

    assert len(cache._cache) == baseline + 1


@pytest.mark.asyncio
async def test_unmapped_model_reuses_the_baseline_entry_for_the_owner(monkeypatch) -> None:
    _policies(monkeypatch)
    cache = AccountSelectionCache(ttl_seconds=60)
    balancer, accounts_repo = _pool(_shared_pool(), cache=cache)

    await balancer.select_account(model=UNMAPPED, api_key_id="K")

    assert len(cache._cache) == 1
    assert accounts_repo.list_calls == 1


@pytest.mark.asyncio
async def test_mapping_removed_between_loads_keeps_the_reserved_account(monkeypatch) -> None:
    # The baseline load filters with the Free mapping; the owner reload sees the mapping removed.
    _policies(monkeypatch, {MODEL: ["free"]}, {})
    balancer, _ = _pool(_shared_pool())

    selection = await balancer.select_account(model=MODEL, api_key_id="K")

    assert selection.account is not None
    assert selection.account.id == "r"


@pytest.mark.asyncio
async def test_opportunistic_admission_exempts_only_the_owner(monkeypatch) -> None:
    _policies(monkeypatch)
    balancer, _ = _pool(_shared_pool())

    async def admit(api_key_id: str | None) -> tuple[str | None, str | None]:
        selection = await balancer.check_opportunistic_admission(
            model=MODEL,
            account_ids=None,
            prefer_earlier_reset_accounts=False,
            routing_strategy="usage_weighted",
            budget_threshold_pct=95.0,
            observe_only=True,
            api_key_id=api_key_id,
        )
        return (selection.account.id if selection.account else None, selection.error_code)

    assert (await admit("K"))[0] == "r"
    # Baseline: a single shared Free account leaves no emergency foreground reserve.
    assert await admit("J") == (None, "opportunistic_burn_window_closed")


@pytest.mark.asyncio
async def test_single_account_pin_honours_only_the_owners_reserved_account(monkeypatch) -> None:
    _policies(monkeypatch)
    balancer, _ = _pool(_shared_pool())

    assert await _picks(balancer, "K", routing_strategy="single_account", account_ids=["r"]) == {"r"}
    assert await _picks(balancer, "K", routing_strategy="single_account", account_ids=["p"]) == {None}


@pytest.mark.parametrize(("outcome", "exempt"), [(None, True), ("hit", True), ("fail_closed", True), ("miss", False)])
def test_websocket_turn_exemption_follows_the_owner_lookup_outcome(outcome, exempt) -> None:
    from app.modules.proxy._service.websocket import mixin as websocket_mixin

    request_state = cast(Any, SimpleNamespace(previous_response_owner_lookup_outcome=outcome, api_key=None))
    key = cast(Any, SimpleNamespace(id="K"))

    assert websocket_mixin._plan_exempt(request_state) is exempt
    assert websocket_mixin._plan_exempt_key_id(request_state, key) == ("K" if exempt else None)
    assert websocket_mixin._plan_exempt_key_id(request_state, None) is None
