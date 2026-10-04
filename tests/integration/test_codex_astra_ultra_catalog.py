from __future__ import annotations

import json
from dataclasses import replace

import pytest
from httpx import AsyncClient

from app.core.openai.model_registry import ReasoningLevel, get_model_registry
from app.core.types import JsonValue
from tests.integration.model_source_helpers import _create_model_source

pytestmark = pytest.mark.integration


@pytest.fixture(
    params=[
        "/backend-api/codex/models",
        "/v1/models?client_version=0.159.1",
        "/api/key-dashboard/models",
    ]
)
def catalog_path(request) -> str:
    return request.param


@pytest.fixture
async def catalog_headers(async_client: AsyncClient) -> dict[str, str]:
    created = await async_client.post("/api/api-keys/", json={"name": "astra-catalog", "limits": []})
    assert created.status_code == 200
    return {"Authorization": f"Bearer {created.json()['key']}"}


@pytest.mark.parametrize(
    "upstream_policy", [{"multi_agent_reasoning_effort": "xhigh"}, {"multi_agent_reasoning_effort": None}, {}]
)
@pytest.mark.parametrize("slug", ["gpt-6-astra", "gpt-6.1-sol"])
async def test_subscription_ultra_advertises_max_without_changing_upstream_metadata(
    async_client: AsyncClient,
    catalog_path: str,
    catalog_headers: dict[str, str],
    upstream_policy: dict[str, JsonValue],
    slug: str,
):
    registry = get_model_registry()
    base = registry.get_models_with_fallback()["gpt-5.6-sol"]
    raw = {**base.raw, **upstream_policy}
    model = replace(base, slug=slug, default_reasoning_level="low", raw=raw)
    await registry.update({"plus": [model]})

    response = await async_client.get(catalog_path, headers=catalog_headers, follow_redirects=True)

    assert response.status_code == 200
    entry = next(item for item in response.json()["models"] if item["slug"] == model.slug)
    assert entry["multi_agent_reasoning_effort"] == "max"
    assert entry["default_reasoning_level"] == "low"
    assert [level["effort"] for level in entry["supported_reasoning_levels"]] == [
        level.effort for level in model.supported_reasoning_levels
    ]
    assert entry["multi_agent_version"] == raw["multi_agent_version"]
    assert entry["tool_mode"] == raw["tool_mode"]
    assert registry.get_models_with_fallback()[model.slug].raw == raw
    assert {key: raw[key] for key in upstream_policy} == upstream_policy
    if not upstream_policy:
        assert "multi_agent_reasoning_effort" not in raw


@pytest.mark.parametrize(
    ("slug", "efforts"),
    [
        ("gpt-6-sol", ("low", "xhigh", "max", "ultra")),
        ("gpt-6-astra", ("low", "xhigh", "ultra")),
        ("gpt-6-astra", ("low", "xhigh", "max")),
        ("gpt-6.1-sol", ("low", "xhigh", "ultra")),
        ("gpt-6.1-sol", ("low", "xhigh", "max")),
    ],
)
async def test_catalog_preserves_multi_agent_effort_outside_subscription_ultra_policy(
    async_client: AsyncClient,
    catalog_path: str,
    catalog_headers: dict[str, str],
    slug: str,
    efforts: tuple[str, ...],
):
    registry = get_model_registry()
    base = registry.get_models_with_fallback()["gpt-5.6-sol"]
    model = replace(
        base,
        slug=slug,
        supported_reasoning_levels=tuple(ReasoningLevel(effort=value, description=value) for value in efforts),
        raw={**base.raw, "multi_agent_reasoning_effort": "xhigh"},
    )
    await registry.update({"plus": [model]})

    response = await async_client.get(catalog_path, headers=catalog_headers, follow_redirects=True)

    assert response.status_code == 200
    entry = next(item for item in response.json()["models"] if item["slug"] == slug)
    assert entry["multi_agent_reasoning_effort"] == "xhigh"


@pytest.mark.parametrize(
    "path",
    ["/backend-api/codex/models/", "/v1/models/?client_version=0.159.1", "/api/key-dashboard/models/"],
)
async def test_catalog_trailing_slashes_keep_existing_not_found_response(
    async_client: AsyncClient, catalog_headers: dict[str, str], path: str
):
    response = await async_client.get(path, headers=catalog_headers)
    assert response.status_code == 404


@pytest.mark.parametrize("slug", ["gpt-6-astra", "gpt-6.1-sol"])
async def test_custom_source_preserves_its_multi_agent_effort(
    async_client: AsyncClient,
    catalog_path: str,
    catalog_headers: dict[str, str],
    slug: str,
):
    await _create_model_source(
        async_client,
        name="custom-ultra-model",
        model=slug,
        base_url="https://source.invalid/v1",
        supports_responses=True,
        raw_metadata_json=json.dumps(
            {
                "supports_reasoning": True,
                "supported_reasoning_levels": ["low", "xhigh", "max", "ultra"],
                "multi_agent_reasoning_effort": "xhigh",
                "multi_agent_version": "v2",
            }
        ),
    )

    response = await async_client.get(catalog_path, headers=catalog_headers, follow_redirects=True)

    assert response.status_code == 200
    entry = next(item for item in response.json()["models"] if item["slug"] == slug)
    assert entry["multi_agent_reasoning_effort"] == "xhigh"
