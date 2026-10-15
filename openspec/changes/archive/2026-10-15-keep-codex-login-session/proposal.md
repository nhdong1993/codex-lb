# Proposal

## Why

The installer replaces `auth.json` with the API key, so users lose their Codex (ChatGPT) login session and its account features. Operators want clients to keep that login while model traffic still goes through codex-lb under the key's policy and limits, without codex-lb storing or depending on the login token, which Codex rotates.

## What Changes

- Proxy authentication accepts the API key from a dedicated `X-Codex-LB-Api-Key` request header, preferred over `Authorization`, so `Authorization` may carry the client's own login token. The header is never forwarded upstream. Key self-service endpoints keep requiring the key in `Authorization`.
- Installer export gains `keep_login=true`: the provider config sends the key through `http_headers`, `cli_auth_credentials_store` is not forced, and `auth.json` is neither created nor replaced.
- The Install tab adds a "keep login session" checkbox, checked by default, with a highlighted Vietnamese warning that Codex sends its login access token to the codex-lb server on every request, and a Vietnamese confirmation before copying or downloading while it is checked.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-keys`: Dedicated API-key header for proxy authentication.
- `api-key-dashboard`: Keep-login installer export and Install tab opt-in with warnings.

## Impact

No schema, settings or dependency changes. Dashboard-visible change to the Install tab. Existing installers and API-key `Authorization` clients are unchanged.
