# Design

## Context

Codex providers with `requires_openai_auth = true` send the signed-in login token as `Authorization` and also send any provider `http_headers`. Verified with Codex CLI 0.162.1: requests to the provider (`/models`, `/responses`) carried both the login bearer and the configured header, while ChatGPT account features went to `chatgpt_base_url` without it.

## Decisions

- Authenticate by the API key in `X-Codex-LB-Api-Key` (lowercase `x-codex-lb-api-key` in config) instead of registering the login token. Token rotation and re-login with another account therefore never break authentication, and codex-lb neither stores nor inspects the login token.
- The dedicated header takes precedence over `Authorization` on proxy HTTP, WebSocket, required-capability and Codex usage-identity paths; an invalid header value is rejected rather than falling back.
- `validate_usage_api_key` (key dashboard, installer export, `/v1/usage`, reset credits, fleet) still reads only `Authorization`, keeping self-service unchanged.
- The header joins `IGNORE_INBOUND_HEADERS`, so every upstream header builder drops it alongside `Authorization`.
- One helper, `proxy_api_authorization` in `app/core/clients/proxy.py`, resolves the credential for auth dependencies, middleware, WebSocket and HTTP-bridge owner forwarding, so replicas forward the API key rather than the login token.
- Keep-login installers carry over only a top-level `cli_auth_credentials_store` (`file`/`keyring`/`auto`) from the previous config so Codex finds the login where it stores it, keep `requires_openai_auth = true`, and never create or replace `auth.json`; Bash uses a staged `auth.new` only to authenticate the catalog download and deletes it.

## Risks / Trade-offs

- The API key is stored in `config.toml` (mode 600 / private ACL), the same exposure as the API-key `auth.json`.
- Codex sends the login access token to codex-lb on every request; codex-lb ignores it but receives it, hence the explicit warning and confirmation.
- Without a login, Codex asks the user to sign in; the installer does not fall back to an API-key `auth.json`.
- The first keep-login install records `auth.json` as `unmanaged`, so the offline uninstaller leaves the current login alone. A later API-key install converts it to a managed restore point using its own pre-replacement copy. Installers exported before this change reject `unmanaged` state and must be re-exported.

## Migration Plan

None. Export a new installer with the option checked.
