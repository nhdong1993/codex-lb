"""Reserved accounts of the requesting API key are exempt from the model Plan filter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast

import pytest

import app.modules.proxy.load_balancer as load_balancer_module
from app.db.models import Account, AccountStatus, AdditionalUsageHistory, UsageHistory
from app.modules.proxy._service.support import _http_bridge_session_supports_service_tier
from app.modules.proxy.account_cache import AccountSelectionCache
from app.modules.proxy.load_balancer import NO_PLAN_SUPPORT_FOR_MODEL, LoadBalancer, RuntimeState
from tests.unit.test_proxy_load_balancer_refresh import (
    StubAccountsRepository,
    StubAdditionalUsageRepository,
    StubStickySessionsRepository,
    StubUsageRepository,
    _additional_entry,
    _make_account,
    _repo_factory,
)

pytestmark = pytest.mark.unit

MODEL = "gpt-x"
SPARK = "gpt-5.3-codex-spark"
_ROUNDS = 8

Outcome = tuple[str | None, str | None, str | None]


@pytest.fixture(autouse=True)
def _isolate_runtime_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_overrides() -> dict[str, str]:
        return {}

    monkeypatch.setattr(load_balancer_module, "_load_dashboard_additional_quota_routing_overrides", _no_overrides)
    monkeypatch.setattr(load_balancer_module, "get_settings", lambda: SimpleNamespace(circuit_breaker_enabled=False))
    monkeypatch.setattr(load_balancer_module, "set_normal", lambda: None)
    monkeypatch.setattr(load_balancer_module, "set_degraded", lambda _reason: None)


@dataclass
class _Registry:
    """Registry stub: the model is offered on ``model_plans`` only."""

    model_plans: frozenset[str] = frozenset({"pro"})
    suppressed: bool = False
    account_plans: dict[str, str] | None = None
    model_account_ids: frozenset[str] | None = None
    tier_plans: dict[str, frozenset[str]] = field(default_factory=dict)
    tier_account_ids: dict[str, frozenset[str]] = field(default_factory=dict)

    def get_snapshot(self) -> Any:
        if self.account_plans is None:
            return None
        return SimpleNamespace(
            account_plans=self.account_plans,
            model_accounts={MODEL: self.model_account_ids or frozenset()},
            model_service_tier_accounts={MODEL: self.tier_account_ids},
        )

    def plan_types_for_model(self, _model: str) -> frozenset[str]:
        return frozenset() if self.suppressed else self.model_plans

    def is_suppressed_model(self, _model: str) -> bool:
        return self.suppressed

    def account_ids_for_model(self, _model: str) -> frozenset[str] | None:
        return self.model_account_ids

    def account_ids_for_model_service_tier(self, _model: str, tier: str | None) -> frozenset[str] | None:
        return self.tier_account_ids.get(tier or "")

    def service_tier_plan_restriction(self, _model: str, tier: str | None) -> frozenset[str] | None:
        return self.tier_plans.get(tier or "")

    def plan_types_for_model_service_tier(self, model: str, tier: str | None) -> frozenset[str]:
        restriction = self.service_tier_plan_restriction(model, tier)
        return self.plan_types_for_model(model) if restriction is None else restriction


def _account(
    account_id: str,
    plan: str,
    *,
    reserved_for: str | None = None,
    status: AccountStatus = AccountStatus.ACTIVE,
) -> Account:
    account = _make_account(account_id, f"{account_id}@example.com")
    account.plan_type = plan
    account.reserved_api_key_id = reserved_for
    account.status = status
    return account


def _usage(accounts: list[Account]) -> StubUsageRepository:
    rows = {
        account.id: UsageHistory(
            id=index,
            account_id=account.id,
            recorded_at=account.last_refresh,
            window="primary",
            used_percent=10.0,
            reset_at=None,
            window_minutes=300,
        )
        for index, account in enumerate(accounts, start=1)
    }
    return StubUsageRepository(primary=rows, secondary={})


OnLoad = Callable[[int, list[Account]], None]


class _AccountsRepository(StubAccountsRepository):
    """Runs ``on_load(call_number, accounts)`` before each ``list_accounts``."""

    def __init__(self, accounts: list[Account], on_load: OnLoad | None = None) -> None:
        super().__init__(accounts)
        self.calls = 0
        self._on_load = on_load

    async def list_accounts(self, *, refresh_existing: bool = False) -> list[Account]:
        self.calls += 1
        if self._on_load is not None:
            self._on_load(self.calls, self._accounts)
        return await super().list_accounts(refresh_existing=refresh_existing)


def _balancer(
    monkeypatch: pytest.MonkeyPatch,
    accounts: list[Account],
    registry: _Registry,
    *,
    additional: dict[str, AdditionalUsageHistory] | None = None,
    cache: AccountSelectionCache | None = None,
    on_load: OnLoad | None = None,
) -> LoadBalancer:
    monkeypatch.setattr(load_balancer_module, "get_model_registry", lambda: registry)
    accounts_repo = _AccountsRepository(accounts, on_load)
    usage_repo = _usage(accounts)
    additional_repo = StubAdditionalUsageRepository(primary=additional or {})
    balancer = LoadBalancer(
        lambda: _repo_factory(accounts_repo, usage_repo, StubStickySessionsRepository(), additional_repo)
    )
    if cache is not None:
        balancer._selection_inputs_cache = cache
    return balancer


async def _picks(
    balancer: LoadBalancer,
    api_key_id: str | None,
    *,
    model: str = MODEL,
    service_tier: str | None = None,
) -> set[str | None]:
    picked: set[str | None] = set()
    for _ in range(_ROUNDS):
        selection = await balancer.select_account(model=model, service_tier=service_tier, api_key_id=api_key_id)
        picked.add(selection.account.id if selection.account else None)
    return picked


async def _outcome(balancer: LoadBalancer, api_key_id: str | None, *, model: str = MODEL) -> Outcome:
    selection = await balancer.select_account(model=model, api_key_id=api_key_id)
    return (selection.account.id if selection.account else None, selection.error_code, selection.error_message)


@pytest.mark.asyncio
async def test_owner_key_uses_reserved_account_outside_model_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    balancer = _balancer(monkeypatch, [_account("r", "plus", reserved_for="K"), _account("p", "pro")], _Registry())

    assert await _picks(balancer, "K") == {"r"}


@pytest.mark.asyncio
async def test_unusable_reserved_account_falls_back_to_plan_filtered_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    accounts = [_account("r", "plus", reserved_for="K"), _account("p", "pro"), _account("c", "plus")]
    balancer = _balancer(monkeypatch, accounts, _Registry())
    balancer._runtime["r"] = RuntimeState(cooldown_until=10**12)

    assert await _picks(balancer, "K") == {"p"}


@pytest.mark.asyncio
async def test_other_keys_and_keyless_keep_the_unexempted_result(monkeypatch: pytest.MonkeyPatch) -> None:
    reserved = _balancer(monkeypatch, [_account("r", "plus", reserved_for="K"), _account("c", "plus")], _Registry())
    oracle = _balancer(monkeypatch, [_account("r", "plus"), _account("c", "plus")], _Registry())

    for api_key_id in ("J", None):
        outcome = await _outcome(reserved, api_key_id)
        assert outcome == await _outcome(oracle, api_key_id)
        assert outcome[1] == NO_PLAN_SUPPORT_FOR_MODEL
    assert await _picks(reserved, "K") == {"r"}


@pytest.mark.asyncio
@pytest.mark.parametrize("owner_plan", ["plus", "pro"])
async def test_continuity_early_return_keeps_the_unexempted_result(
    monkeypatch: pytest.MonkeyPatch, owner_plan: str
) -> None:
    # A paused account only reaches the continuity-owner pool; Plan "pro" is the in-Plan control.
    def accounts(reserved_for: str | None) -> list[Account]:
        paused = _account("r", owner_plan, reserved_for=reserved_for, status=AccountStatus.PAUSED)
        return [paused, _account("c", "plus")]

    reserved = _balancer(monkeypatch, accounts("K"), _Registry())
    oracle = _balancer(monkeypatch, accounts(None), _Registry())

    for api_key_id in ("J", None):
        outcome = await _outcome(reserved, api_key_id)
        if owner_plan == "plus":
            assert outcome == await _outcome(oracle, api_key_id)
            assert outcome[1] == NO_PLAN_SUPPORT_FOR_MODEL
        else:
            # An in-Plan continuity owner empties the pool without a Plan error, today and after the change.
            assert outcome[:2] == (None, None)


@pytest.mark.asyncio
async def test_suppressed_model_is_not_exempted(monkeypatch: pytest.MonkeyPatch) -> None:
    accounts = [_account("r", "plus", reserved_for="K"), _account("p", "pro")]
    balancer = _balancer(monkeypatch, accounts, _Registry(suppressed=True))

    assert await _picks(balancer, "K") == {None}


@pytest.mark.asyncio
async def test_service_tier_exemption_follows_tier_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    def accounts() -> list[Account]:
        return [_account("r", "plus", reserved_for="K"), _account("p", "pro")]

    restricted = _balancer(monkeypatch, accounts(), _Registry(tier_plans={"priority": frozenset({"pro"})}))
    assert await _picks(restricted, "K", service_tier="priority") == {"p"}

    fallback = _balancer(monkeypatch, accounts(), _Registry())
    assert await _picks(fallback, "K", service_tier="priority") == {"r"}
    assert await _picks(fallback, "K", service_tier="ultrafast") == {"p"}

    covered = {"r": "plus", "p": "pro"}
    entitled_registry = _Registry(
        account_plans=covered,
        model_account_ids=frozenset(covered),
        tier_account_ids={"ultrafast": frozenset({"r"})},
    )
    entitled = _balancer(monkeypatch, accounts(), entitled_registry)
    assert await _picks(entitled, "K", service_tier="ultrafast") == {"r"}


@pytest.mark.asyncio
async def test_known_account_catalog_omission_is_not_exempted(monkeypatch: pytest.MonkeyPatch) -> None:
    def accounts() -> list[Account]:
        return [_account("r", "plus", reserved_for="K"), _account("p", "pro"), _account("n", "pro")]

    # ``n`` is not in the snapshot, so the pool-wide catalog index is skipped; r's own catalog still omits the model.
    known_registry = _Registry(account_plans={"r": "plus", "p": "pro"}, model_account_ids=frozenset({"p"}))
    known = _balancer(monkeypatch, accounts(), known_registry)
    assert "r" not in await _picks(known, "K")

    unknown_registry = _Registry(account_plans={"p": "pro"}, model_account_ids=frozenset({"p"}))
    unknown = _balancer(monkeypatch, accounts(), unknown_registry)
    assert await _picks(unknown, "K") == {"r"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("with_pool_account", "telemetry"),
    [(False, {}), (True, {"p": 100.0}), (True, {"r": 5.0})],
    ids=["only-reserved", "pool-exhausted", "pool-missing-telemetry"],
)
async def test_spark_other_keys_keep_the_unexempted_result(
    monkeypatch: pytest.MonkeyPatch, with_pool_account: bool, telemetry: dict[str, float]
) -> None:
    def accounts(reserved_for: str | None) -> list[Account]:
        pool = [_account("p", "pro")] if with_pool_account else []
        return [_account("r", "business", reserved_for=reserved_for), *pool]

    additional = {
        account_id: _additional_entry(index, account_id=account_id, window="primary", used_percent=used)
        for index, (account_id, used) in enumerate(telemetry.items(), start=1)
    }
    reserved = _balancer(monkeypatch, accounts("K"), _Registry(), additional=additional)
    oracle = _balancer(monkeypatch, accounts(None), _Registry(), additional=additional)

    for api_key_id in ("J", None):
        assert await _outcome(reserved, api_key_id, model=SPARK) == await _outcome(oracle, api_key_id, model=SPARK)
    if "r" in telemetry:
        assert await _picks(reserved, "K", model=SPARK) == {"r"}


@pytest.mark.asyncio
async def test_opportunistic_admission_applies_the_exemption_to_the_owner_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def accounts(reserved_for: str | None) -> list[Account]:
        return [_account("r", "plus", reserved_for=reserved_for), _account("c", "plus")]

    async def admit(balancer: LoadBalancer, api_key_id: str | None) -> Outcome:
        selection = await balancer.check_opportunistic_admission(
            model=MODEL,
            account_ids=None,
            prefer_earlier_reset_accounts=False,
            routing_strategy="usage_weighted",
            budget_threshold_pct=95.0,
            observe_only=True,
            api_key_id=api_key_id,
        )
        return (selection.account.id if selection.account else None, selection.error_code, selection.error_message)

    reserved = _balancer(monkeypatch, accounts("K"), _Registry())
    oracle = _balancer(monkeypatch, accounts(None), _Registry())

    assert await admit(reserved, "J") == await admit(oracle, "J")
    assert (await admit(reserved, "K"))[0] == "r"


@pytest.mark.asyncio
async def test_only_the_owner_key_adds_a_selection_cache_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AccountSelectionCache(ttl_seconds=60)
    accounts = [_account("r", "plus", reserved_for="K"), _account("p", "pro")]
    balancer = _balancer(monkeypatch, accounts, _Registry(), cache=cache)

    await balancer.select_account(model=MODEL, api_key_id="J")
    await balancer.select_account(model=MODEL, api_key_id=None)
    baseline_entries = len(cache._cache)
    await balancer.select_account(model=MODEL, api_key_id="K")
    await balancer.select_account(model=MODEL, api_key_id="K")
    assert len(cache._cache) == baseline_entries + 1

    # Without a model there is no Plan filter, so the owner needs no second load.
    await balancer.select_account(model=None, api_key_id="J")
    await balancer.select_account(model=None, api_key_id="K")
    assert len(cache._cache) == baseline_entries + 2


@pytest.mark.asyncio
@pytest.mark.parametrize(("new_owner", "expected"), [("K", "r"), (None, "p"), ("J", "p")])
async def test_exemption_follows_the_reservation_read_by_the_owner_load(
    monkeypatch: pytest.MonkeyPatch, new_owner: str | None, expected: str
) -> None:
    def change_reservation(call: int, accounts: list[Account]) -> None:
        if call >= 2:
            next(account for account in accounts if account.id == "r").reserved_api_key_id = new_owner

    accounts = [_account("r", "plus", reserved_for="K"), _account("p", "pro")]
    balancer = _balancer(monkeypatch, accounts, _Registry(), on_load=change_reservation)

    selection = await balancer.select_account(model=MODEL, api_key_id="K")

    assert selection.account is not None
    assert selection.account.id == expected


def test_bridge_reuse_exempts_only_the_request_keys_reserved_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _Registry()
    monkeypatch.setattr("app.modules.proxy._service.support.get_model_registry", lambda: registry)
    session = cast(Any, SimpleNamespace(account=_account("r", "plus", reserved_for="K")))
    session.catalog_omission_quota_admission = None

    def supported(exempt: frozenset[str], tier: str | None = None) -> bool:
        return _http_bridge_session_supports_service_tier(
            session, request_model=MODEL, request_service_tier=tier, plan_exempt_account_ids=exempt
        )

    assert supported(frozenset({"r"})) is True
    assert supported(frozenset()) is False
    assert supported(frozenset({"r"}), "ultrafast") is False

    registry.account_plans = {"r": "plus"}
    registry.model_account_ids = frozenset({"p"})
    assert supported(frozenset({"r"})) is False


@pytest.mark.asyncio
async def test_exemption_reads_the_reserved_accounts_own_catalog_when_coverage_is_partial() -> None:
    from dataclasses import replace

    from app.core.openai.model_registry import ModelRegistry
    from app.modules.proxy._load_balancer.model_eligibility import plan_exemption_applies

    registry = ModelRegistry(ttl_seconds=60.0)
    model = replace(registry.get_models_with_fallback()["gpt-5.4"], raw={})
    # ``r`` was fetched and does not advertise the model; ``n`` could not be fetched.
    await registry.update(
        {"pro": [model]},
        per_account_results={"p": ("pro", [model]), "r": ("plus", [])},
        active_account_plans={"p": "pro", "r": "plus", "n": "plus"},
    )
    assert registry.account_ids_for_model("gpt-5.4") is None

    assert plan_exemption_applies("r", "gpt-5.4", registry=registry, service_tier=None) is False
    assert plan_exemption_applies("n", "gpt-5.4", registry=registry, service_tier=None) is True


@pytest.mark.asyncio
async def test_plan_exempt_spark_account_uses_the_spark_quota_window(monkeypatch: pytest.MonkeyPatch) -> None:
    spark = _additional_entry(1, account_id="r", window="primary", used_percent=5.0)
    accounts = [_account("r", "business", reserved_for="K"), _account("p", "pro")]
    balancer = _balancer(monkeypatch, accounts, _Registry(), additional={"r": spark})

    inputs = await balancer._load_selection_inputs(model=SPARK, plan_exempt_api_key_id="K")

    assert "r" in inputs.ignore_standard_quota_account_ids
    assert isinstance(inputs.latest_primary["r"], AdditionalUsageHistory)
    assert inputs.latest_primary["r"].used_percent == spark.used_percent


@pytest.mark.asyncio
async def test_exemption_reads_the_reserved_accounts_own_tier_evidence_when_coverage_is_partial() -> None:
    from dataclasses import replace

    from app.core.openai.model_registry import ModelRegistry
    from app.modules.proxy._load_balancer.model_eligibility import plan_exemption_applies

    registry = ModelRegistry(ttl_seconds=60.0)
    base = registry.get_models_with_fallback()["gpt-5.4"]
    fast = replace(base, raw={"service_tiers": [{"id": "priority", "name": "Fast"}]})
    no_fast = replace(base, raw={"service_tiers": [{"slug": "default"}]})
    # ``r`` was fetched without ``priority``; ``n`` could not be fetched.
    await registry.update(
        {"pro": [fast]},
        per_account_results={"p": ("pro", [fast]), "r": ("pro", [no_fast])},
        active_account_plans={"p": "pro", "r": "pro", "n": "plus"},
    )
    assert registry.account_ids_for_model_service_tier("gpt-5.4", "priority") is None

    assert plan_exemption_applies("r", "gpt-5.4", registry=registry, service_tier="priority") is False
    assert plan_exemption_applies("r", "gpt-5.4", registry=registry, service_tier=None) is True
    assert plan_exemption_applies("n", "gpt-5.4", registry=registry, service_tier="priority") is True


@pytest.mark.asyncio
async def test_undiscovered_quota_model_keeps_the_baseline_quota_window(monkeypatch: pytest.MonkeyPatch) -> None:
    spark = _additional_entry(1, account_id="r", window="primary", used_percent=5.0)
    accounts = [_account("r", "business", reserved_for="K")]
    balancer = _balancer(monkeypatch, accounts, _Registry(model_plans=frozenset()), additional={"r": spark})

    baseline = await balancer._load_selection_inputs(model=SPARK)
    owner = await balancer._load_selection_inputs(model=SPARK, plan_exempt_api_key_id="K")

    assert owner.ignore_standard_quota_account_ids == baseline.ignore_standard_quota_account_ids
    assert type(owner.latest_primary["r"]) is type(baseline.latest_primary["r"])


@pytest.mark.asyncio
@pytest.mark.parametrize(("still_reserved", "expected_scope"), [(True, ("r",)), (False, None)])
async def test_owner_overrides_apply_only_while_the_reload_still_sees_the_reservation(
    still_reserved: bool, expected_scope: tuple[str, ...] | None
) -> None:
    from app.modules.proxy._load_balancer.reserved_accounts import load_inputs_for_key

    calls: list[dict[str, Any]] = []

    async def load(**kwargs: Any) -> Any:
        calls.append(kwargs)
        owner = "K" if len(calls) == 1 or still_reserved else None
        account = _account("r", "plus", reserved_for=owner)
        scope = kwargs.get("account_ids")
        return load_balancer_module._SelectionInputs(
            accounts=[account] if scope is None or "r" in scope else [],
            latest_primary={},
            latest_secondary={},
            latest_monthly={},
            runtime_accounts=[account],
        )

    await load_inputs_for_key(load, "K", model=MODEL, account_ids=None, owner_overrides={"account_ids": ("r",)})

    # The last load is the one whose result is used.
    assert calls[-1].get("account_ids") == expected_scope
