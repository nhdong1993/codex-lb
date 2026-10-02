## Why

Native model-source WebSockets inherit a 20-second pong deadline that can terminate a healthy streamed response when a sequential provider defers reading control frames until generation finishes. Production CLIProxyAPI failures cluster around 42–44 seconds after connecting, while the provider is still writing response events.

## What Changes

- Retain WebSocket keepalive pings without an independent pong deadline; existing first-frame, stream-idle and total-turn budgets continue to bound stalled work.
- Assert the explicit connection option and verify delayed pongs, actual disconnects and silent streams through public-route regression tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-source-websocket`: response progress and existing request deadlines govern source liveness when a provider defers pongs.

## Impact

Source WebSocket connection setup, unit/integration tests and capability context. Error sanitization and logging retain their existing behavior. No new settings, schema changes, source switching or automatic replay. Production deployment remains a separate operation.
