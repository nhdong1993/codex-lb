from __future__ import annotations

import tomllib

import pytest

from app.db.session import SessionLocal
from app.modules.api_keys.repository import ApiKeysRepository
from app.modules.api_keys.service import ApiKeyCreateData, ApiKeyCreatedData, ApiKeysService
from tests.integration.model_source_helpers import _enable_api_key_auth

pytestmark = pytest.mark.integration

# A client keeping its own Codex login sends that login token as Authorization.
LOGIN = {"Authorization": "Bearer eyJ.client-login-access-token.sig", "chatgpt-account-id": "personal-account"}


async def _create_api_key(name: str) -> ApiKeyCreatedData:
    async with SessionLocal() as session:
        return await ApiKeysService(ApiKeysRepository(session)).create_key(
            ApiKeyCreateData(name=name, allowed_models=None, limits=[])
        )


@pytest.mark.asyncio
async def test_dedicated_api_key_header_authenticates_beside_client_login(async_client, db_setup):
    del db_setup
    await _enable_api_key_auth(async_client)
    key = await _create_api_key("keep-login-client")
    with_key = {**LOGIN, "X-Codex-LB-Api-Key": key.key}

    assert (await async_client.get("/v1/models", headers=LOGIN)).status_code == 401
    assert (await async_client.get("/v1/models", headers=with_key)).status_code == 200
    assert (await async_client.get("/backend-api/codex/models", headers=with_key)).status_code == 200
    usage = await async_client.get("/api/codex/usage", headers=with_key)
    assert usage.status_code == 200

    # The dedicated header wins, so an invalid value is rejected even beside a valid Authorization key.
    invalid = await async_client.get(
        "/v1/models", headers={"Authorization": f"Bearer {key.key}", "X-Codex-LB-Api-Key": "sk-clb-wrong"}
    )
    assert invalid.status_code == 401
    assert key.key not in invalid.text


@pytest.mark.asyncio
async def test_key_self_service_still_requires_authorization_api_key(async_client, db_setup):
    del db_setup
    key = await _create_api_key("self-service-key")
    response = await async_client.get("/api/key-dashboard/profile", headers={**LOGIN, "X-Codex-LB-Api-Key": key.key})
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("keep_login", [False, True])
async def test_keep_login_installer_sends_key_in_dedicated_header(async_client, db_setup, keep_login):
    del db_setup
    key = await _create_api_key("keep-login-installer")
    path = "/api/key-dashboard/install-script?platform=linux" + ("&keep_login=true" if keep_login else "")
    response = await async_client.get(path, headers={"Authorization": f"Bearer {key.key}"})
    assert response.status_code == 200
    config = tomllib.loads(response.text.split("<<'CODEX_LB_CONFIG'\n", 1)[1].split("CODEX_LB_CONFIG\n", 1)[0])
    provider = config["model_providers"]["codex-lb"]
    if keep_login:
        assert provider["http_headers"] == {"x-codex-lb-api-key": key.key}
        assert "cli_auth_credentials_store" not in config
    else:
        assert "http_headers" not in provider
        assert config["cli_auth_credentials_store"] == "file"
