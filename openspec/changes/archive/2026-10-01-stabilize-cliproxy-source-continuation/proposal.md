## Why

The deployed CLIProxyAPI pool intermittently returns completed responses that ignore tool results. A direct probe of credential slot 4 reproduced a zero-input completion from full tool history, and a subsequent probe on that credential ended before a terminal event.

## What Changes

- Quarantine the failing credential with its existing routing weight control, retaining the credential for operator recovery.
- Enable CLIProxyAPI's existing session affinity so healthy conversations do not rotate credentials on every turn.
- Verify tool-result content and terminal events through the deployed codex-lb source, and record the operating constraints.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a deployment configuration repair and operational documentation of existing capabilities; codex-lb routing, ownership, API and schema contracts remain unchanged.

## Impact

CLIProxyAPI runtime configuration and operational context for model-source-routing. Session affinity is a CLIProxyAPI-wide setting with the existing weighted selector as fallback. No application rebuild, HA backend restart, token replacement or ownership-table rewrite is required.
