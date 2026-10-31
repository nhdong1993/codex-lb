from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

import app.modules.proxy.load_balancer as load_balancer_module
from app.db.models import Account, AccountStatus, UsageHistory
from app.modules.proxy._load_balancer.reserved_accounts import drop_foreign_reserved
from app.modules.proxy.account_cache import AccountSelectionCache
from app.modules.proxy.load_balancer import LoadBalancer
from tests.unit.test_load_balancer_contract import _account, _balancer, _usage_row

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _isolate_runtime_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(load_balancer_module, "get_settings", lambda: SimpleNamespace(circuit_breaker_enabled=False))
    monkeypatch.setattr(load_balancer_module, "set_normal", lambda: None)
    monkeypatch.setattr(load_balancer_module, "set_degraded", lambda _reason: None)


@pytest.fixture
def selection_cache() -> AccountSelectionCache:
    return AccountSelectionCache(ttl_seconds=60)


# Weighted strategies draw at random; repeated picks make a wrong candidate show up.
_ROUNDS = 12


def _reserved(account_id: str, api_key_id: str) -> Account:
    account = _account(account_id)
    account.reserved_api_key_id = api_key_id
    return account


def _pool(selection_cache: AccountSelectionCache, *, a_used: float, b_used: float, a_status=AccountStatus.ACTIVE):
    reserved = _reserved("acc-a", "key-k")
    reserved.status = a_status
    primary: dict[str, UsageHistory] = {
        "acc-a": _usage_row(1, "acc-a", window="primary", used_percent=a_used),
        "acc-b": _usage_row(2, "acc-b", window="primary", used_percent=b_used),
    }
    balancer, _, _, _ = _balancer([reserved, _account("acc-b")], selection_cache, primary=primary)
    return balancer


async def _picks(
    balancer: LoadBalancer,
    api_key_id: str | None,
    *,
    routing_strategy: load_balancer_module.RoutingStrategy = "usage_weighted",
    account_ids: list[str] | None = None,
) -> set[str | None]:
    picked: set[str | None] = set()
    for _ in range(_ROUNDS):
        selection = await balancer.select_account(
            routing_strategy=routing_strategy, api_key_id=api_key_id, account_ids=account_ids
        )
        picked.add(selection.account.id if selection.account else None)
    return picked


@pytest.mark.asyncio
async def test_select_account_excludes_account_reserved_for_other_key(selection_cache: AccountSelectionCache) -> None:
    balancer = _pool(selection_cache, a_used=1.0, b_used=60.0)

    assert await _picks(balancer, "key-j") == {"acc-b"}


@pytest.mark.asyncio
async def test_select_account_without_api_key_excludes_reserved_accounts(
    selection_cache: AccountSelectionCache,
) -> None:
    balancer = _pool(selection_cache, a_used=1.0, b_used=60.0)

    assert await _picks(balancer, None) == {"acc-b"}


@pytest.mark.asyncio
@pytest.mark.parametrize("a_used", [80.0, 97.0])
async def test_select_account_prefers_reserved_account_for_owner_key(
    selection_cache: AccountSelectionCache, a_used: float
) -> None:
    balancer = _pool(selection_cache, a_used=a_used, b_used=5.0)

    assert await _picks(balancer, "key-k") == {"acc-a"}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [AccountStatus.QUOTA_EXCEEDED, AccountStatus.PAUSED, AccountStatus.DEACTIVATED])
async def test_select_account_reserved_quota_exceeded_falls_back_to_pool(
    selection_cache: AccountSelectionCache, status: AccountStatus
) -> None:
    balancer = _pool(selection_cache, a_used=10.0, b_used=50.0, a_status=status)

    assert await _picks(balancer, "key-k") == {"acc-b"}


@pytest.mark.asyncio
async def test_select_account_reserved_cooldown_falls_back_to_pool(selection_cache: AccountSelectionCache) -> None:
    balancer = _pool(selection_cache, a_used=10.0, b_used=50.0)
    balancer._runtime["acc-a"] = load_balancer_module.RuntimeState(cooldown_until=time.time() + 600)

    assert await _picks(balancer, "key-k") == {"acc-b"}


@pytest.mark.asyncio
async def test_foreign_key_selection_keeps_reserved_account_runtime_state(
    selection_cache: AccountSelectionCache,
) -> None:
    balancer = _pool(selection_cache, a_used=10.0, b_used=50.0)
    cooldown_until = time.time() + 600
    balancer._runtime["acc-a"] = load_balancer_module.RuntimeState(cooldown_until=cooldown_until)

    assert await _picks(balancer, "key-j") == {"acc-b"}
    assert balancer._runtime["acc-a"].cooldown_until == cooldown_until
    assert await _picks(balancer, "key-k") == {"acc-b"}


@pytest.mark.asyncio
async def test_required_owner_reserved_for_other_key_fails_closed(selection_cache: AccountSelectionCache) -> None:
    balancer = _pool(selection_cache, a_used=10.0, b_used=50.0)

    selection = await balancer.select_account(
        routing_strategy="usage_weighted",
        api_key_id="key-j",
        required_account_id="acc-a",
        required_continuity_owner=True,
    )

    assert selection.account is None
    assert selection.error_code == "continuity_owner_policy_conflict"


@pytest.mark.asyncio
async def test_single_account_routing_ignores_reservation_preference(selection_cache: AccountSelectionCache) -> None:
    balancer = _pool(selection_cache, a_used=10.0, b_used=50.0)

    # The proxy service scopes single_account routing to the configured account id.
    picked = await _picks(balancer, "key-k", routing_strategy="single_account", account_ids=["acc-b"])

    assert picked == {"acc-b"}


def test_drop_foreign_reserved_is_noop_without_reservations() -> None:
    inputs = load_balancer_module._SelectionInputs(
        accounts=[_account("acc-a"), _reserved("acc-b", "key-k")],
        latest_primary={},
        latest_secondary={},
        latest_monthly={},
    )

    assert drop_foreign_reserved(inputs, "key-k") is inputs
    dropped = drop_foreign_reserved(inputs, "key-j")
    assert [account.id for account in dropped.accounts] == ["acc-a"]
    assert [account.id for account in dropped.runtime_accounts or []] == ["acc-a", "acc-b"]
    assert dropped.effective_sticky_mutation_authority_account_ids == frozenset({"acc-a"})
