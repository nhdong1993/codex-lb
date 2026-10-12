## Why

An HTTP-only source can repeatedly reject upstream WebSocket handshakes while a Codex client keeps retrying. An in-band error after upgrade cannot trigger the client's immediate HTTP 426 fallback, and newer clients choose transport from provider capability rather than per-model catalog preference.

## What Changes

- Reject ordinary WebSocket upgrades with HTTP 426 for authenticated source-only keys whose effective permitted source models do not all support WebSocket, matching installer policy.
- Preserve authentication/firewall ordering, required-capability routing and mixed subscription/source keys.
- Document the HTTP-only source flag and dedicated HTTP provider configuration for mixed keys.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-source-websocket`: pre-upgrade HTTP fallback for source-only scope.

## Impact

Shared Responses handshake guard, route tests and operational context. No schema, new environment setting, global WebSocket disablement or automatic conversion of accepted WebSocket turns.
