from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.clients.proxy import ProxyResponseError
from app.core.errors import openai_error
from app.core.model_plan_policy import ModelPlanPolicies
from app.core.openai.model_registry import ModelRegistry, UpstreamModel
from app.core.openai.requests import ResponsesCompactRequest, ResponsesRequest
from app.db.models import DashboardSettings
from app.modules.proxy import model_admission
from app.modules.proxy.request_policy import apply_model_plan_service_tier_fallback

pytestmark = pytest.mark.unit

MODEL = "gpt-6-luna"
_TIER_KEYS = ("service_tiers", "additional_speed_tiers", "default_service_tier")


def _catalog_model(*, tiers: tuple[str, ...]) -> UpstreamModel:
    base = ModelRegistry(ttl_seconds=60).get_models_with_fallback()[MODEL]
    raw = {key: value for key, value in base.raw.items() if key not in _TIER_KEYS}
    if tiers:
        raw["service_tiers"] = [{"id": tier, "name": tier} for tier in tiers]
    return replace(base, raw=raw)


async def _registry(*, plus_tiers: tuple[str, ...] = ("priority",), free_catalog: bool = True) -> ModelRegistry:
    registry = ModelRegistry(ttl_seconds=60)
    free = _catalog_model(tiers=())
    plus = _catalog_model(tiers=plus_tiers)
    per_plan: dict[str, list[UpstreamModel]] = {"plus": [plus]}
    per_account: dict[str, tuple[str, list[UpstreamModel]]] = {"acc-plus": ("plus", [plus])}
    if free_catalog:
        per_plan["free"] = [free]
        per_account["acc-free"] = ("free", [free])
    await registry.update(
        per_plan,
        per_account_results=per_account,
        active_account_plans={"acc-plus": "plus", "acc-free": "free"},
    )
    return registry


@pytest.fixture
def policies(monkeypatch: pytest.MonkeyPatch) -> ModelPlanPolicies:
    current: ModelPlanPolicies = {MODEL: ["free"]}

    async def snapshot() -> tuple[DashboardSettings, ModelPlanPolicies]:
        return DashboardSettings(), current

    monkeypatch.setattr(model_admission, "routing_policy_snapshot", snapshot)
    return current


def _request(service_tier: str | None, *, model: str = MODEL) -> ResponsesRequest:
    return ResponsesRequest(model=model, instructions="ping", input=[], service_tier=service_tier)


@pytest.mark.asyncio
@pytest.mark.parametrize("service_tier", ["priority", "fast"])
async def test_drops_a_tier_no_allowed_plan_offers(policies: ModelPlanPolicies, service_tier: str) -> None:
    registry = await _registry()
    payload = _request(service_tier)

    assert await apply_model_plan_service_tier_fallback(payload, registry=registry)
    assert payload.service_tier is None
    assert "service_tier" not in payload.to_payload()


@pytest.mark.asyncio
async def test_drops_the_tier_of_a_compact_request(policies: ModelPlanPolicies) -> None:
    registry = await _registry()
    payload = ResponsesCompactRequest(model=MODEL, instructions="ping", input=[], service_tier="priority")

    assert await apply_model_plan_service_tier_fallback(payload, registry=registry)
    assert payload.service_tier is None


@pytest.mark.asyncio
async def test_drops_the_tier_when_the_recognized_model_advertises_no_tiers(policies: ModelPlanPolicies) -> None:
    registry = await _registry(plus_tiers=())
    payload = _request("ultrafast")

    assert await apply_model_plan_service_tier_fallback(payload, registry=registry)
    assert payload.service_tier is None


@pytest.mark.asyncio
async def test_keeps_the_tier_when_an_allowed_plan_offers_it(policies: ModelPlanPolicies) -> None:
    policies[MODEL] = ["free", "plus"]
    registry = await _registry()
    payload = _request("priority")

    assert not await apply_model_plan_service_tier_fallback(payload, registry=registry)
    assert payload.service_tier == "priority"


@pytest.mark.asyncio
async def test_keeps_an_explicit_tier_for_an_unconfigured_model(policies: ModelPlanPolicies) -> None:
    policies.clear()
    registry = await _registry()
    payload = _request("priority")

    assert not await apply_model_plan_service_tier_fallback(payload, registry=registry)
    assert payload.service_tier == "priority"


@pytest.mark.asyncio
async def test_keeps_the_tier_without_a_catalog_snapshot(policies: ModelPlanPolicies) -> None:
    payload = _request("priority")

    assert not await apply_model_plan_service_tier_fallback(payload, registry=ModelRegistry(ttl_seconds=60))
    assert payload.service_tier == "priority"


@pytest.mark.asyncio
async def test_keeps_the_tier_when_account_catalogs_are_not_authoritative(policies: ModelPlanPolicies) -> None:
    # The active Free account has no fetched catalog, so coverage is incomplete.
    registry = await _registry(free_catalog=False)
    snapshot = registry.get_snapshot()
    assert snapshot is not None and not snapshot.account_catalogs_authoritative
    payload = _request("priority")

    assert not await apply_model_plan_service_tier_fallback(payload, registry=registry)
    assert payload.service_tier == "priority"


@pytest.mark.asyncio
async def test_keeps_the_tier_for_a_model_unknown_to_the_catalog(policies: ModelPlanPolicies) -> None:
    policies["operator-mapped-unknown"] = ["free"]
    registry = await _registry()
    payload = _request("priority", model="operator-mapped-unknown")

    assert not await apply_model_plan_service_tier_fallback(payload, registry=registry)
    assert payload.service_tier == "priority"


@pytest.mark.asyncio
async def test_keeps_the_tier_when_the_routing_policy_cannot_be_read(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_snapshot() -> tuple[DashboardSettings, ModelPlanPolicies]:
        raise ProxyResponseError(503, openai_error("upstream_unavailable", "policy unavailable"))

    monkeypatch.setattr(model_admission, "routing_policy_snapshot", failing_snapshot)
    registry = await _registry()
    payload = _request("priority")

    assert not await apply_model_plan_service_tier_fallback(payload, registry=registry)
    assert payload.service_tier == "priority"


@pytest.mark.asyncio
@pytest.mark.parametrize("service_tier", [None, "auto", "default"])
async def test_omitted_or_default_tier_does_not_read_the_policy(
    monkeypatch: pytest.MonkeyPatch, service_tier: str | None
) -> None:
    async def unexpected_snapshot() -> tuple[DashboardSettings, ModelPlanPolicies]:
        raise AssertionError("the policy must not be read for an omit-equivalent tier")

    monkeypatch.setattr(model_admission, "routing_policy_snapshot", unexpected_snapshot)
    payload = _request(service_tier)

    assert not await apply_model_plan_service_tier_fallback(payload, registry=await _registry())
    assert payload.service_tier == service_tier
