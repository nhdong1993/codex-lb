## Why

Review reproduced source compact output being sent to a subscription account
when the same request carries that account's previous-response anchor. The
subscription/file exclusions skip source ownership validation, so authoritative
source state can cross credentials despite its durable owner record.

## What Changes

- Check durable source references before any fallback to subscription dispatch
  on the standalone compact and HTTP Responses routes, including file exclusions
  and subscription continuity suppression.
- Preserve subscription routing when no source-owned reference conflicts.
- Return the existing ownership error before reservation or dispatch for mixed
  ownership; keep disabled-source checks separate from continuity precedence.
- Regress both compact endpoints and HTTP continuation/trigger surfaces for
  previous-response, turn-state and uploaded-file ownership.

## Capabilities

### Modified Capabilities

- `model-source-routing`: subscription continuity cannot override a conflicting
  retained source reference.

## Impact

HTTP proxy routing and integration tests only. No new configuration, schema,
credential change or deployment.
