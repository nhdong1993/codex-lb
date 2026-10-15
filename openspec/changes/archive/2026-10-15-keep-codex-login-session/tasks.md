# Tasks

## 1. Header authentication

- [x] 1.1 Prefer `X-Codex-LB-Api-Key` over `Authorization` on proxy HTTP, WebSocket, required-capability and usage-identity authentication; keep self-service on `Authorization`.
- [x] 1.2 Drop the header from every upstream request.

## 2. Installer and Install tab

- [x] 2.1 Add `keep_login` export: provider `http_headers`, no forced credential store, no `auth.json` changes on Bash/Python and PowerShell.
- [x] 2.2 Add the default-checked checkbox, highlighted Vietnamese warning, and Vietnamese confirmation before copy/download.

## 3. Verification

- [x] 3.1 Cover header precedence, self-service rejection, upstream dropping, WebSocket auth, installer keep-login files, and the Install tab; run lint, type checks, and strict OpenSpec validation.

## Verification Notes

- Codex CLI 0.162.1 against a local header-capturing server with a fake ChatGPT `auth.json` (`"auth_mode": "chatgpt"`): `/models`, the `/responses` WebSocket handshake, and HTTP `/responses` all carried the login bearer plus `x-codex-lb-api-key`; account features went to `chatgpt_base_url` without it.
- `tests/integration/test_proxy_api_key_header.py`: header auth beside a login bearer (`/v1/models`, `/backend-api/codex/models`, `/api/codex/usage`), header precedence, self-service rejection, keep-login export config.
- `tests/unit/test_key_dashboard_install.py` keep-login: `auth.json` unchanged or absent, no staged `auth.new` left, `http_headers` set, no credential store, inert TOML value (PowerShell cases skipped: no pwsh here).
- `tests/unit/test_proxy_utils.py` / `test_proxy_api_websocket_auth.py`: header dropped upstream; WebSocket prefers the header.
- Backend regression (auth, key dashboard, firewall, usage, websocket responses): 563 passed, 1 failed — `test_registered_proxy_route_inventory_has_one_explicit_capability_policy`, which fails identically on clean HEAD.
- Frontend: key-dashboard flow 15 passed; screenshots via `frontend/screenshots/key-install-keep-login.config.ts`.
- Review follow-ups: HTTP-bridge owner forwarding uses the codex-lb key (`test_stream_http_responses_forwards_codex_lb_credential_not_client_login`); keep-login uninstall leaves renewed logins, API-key reinstall restores the pre-replacement login, top-level credential store carried over (`test_key_dashboard_install.py`); pending export confirmations are cancelled by newer ones.
- Post-review re-runs: auth deps/proxy utils/websocket auth/bridge forwarding unit 1501 passed (`dedicated_api_key_authorization` keeps the HTTPBearer contract); full `test_proxy_http_bridge.py` passed; integration subset (header, key dashboard, install catalog, daybreak, auth middleware, codex usage) 216 passed, 1 failed (pre-existing route inventory, also failing on clean HEAD).
- `tests/integration/test_http_responses_bridge.py`: 172 passed (an earlier run under concurrent load showed a transient cascade around the full-resend classification tests; they pass in isolation and in the full re-run).
- Main specs already carry the ADDED requirements; archive with `--skip-specs`.
