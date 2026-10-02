## Why

The pong-timeout fix leaves one pending ping future per interval when providers never send pongs, accumulating across successful turns on a reused connection. It also lacks public-route regression coverage and its archived proposal overstates implemented diagnostics.

## What Changes

- Reproduce delayed-pong behavior through real local upstream sockets and both public route families, including their trailing-slash forms.
- Bound keepalive bookkeeping independently of connection lifetime while preserving periodic pings and response deadlines.
- Verify first-frame and stream-idle timeouts, disconnection settlement and no replay with pongs withheld.
- Correct documentation scope and distinguish the suspected production cause from the synthetic regression evidence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-source-websocket`: keepalive resources remain bounded across repeated turns with unanswered pings.

## Impact

Source WebSocket transport, integration tests and OpenSpec context/review evidence. No new settings or deployment.
