## Why

Review of prompt plan verification reproduced four gaps: PostgreSQL can revive old work after credential replacement, reused WebSockets bypass model exclusion, completed checks swallow fresh Free evidence, and cancelled workers leave OAuth refresh running during shutdown.

## What Changes

- Serialize priority evidence writes with credential replacement on the account row.
- Reopen completed checks for new Free evidence using the remaining attempt budget and original expiry.
- Apply model exclusion before sending another request over an existing WebSocket, preserving hard owners and accepted siblings.
- Drain shared authentication refresh safely when priority verification is cancelled or times out.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `usage-refresh-policy`: replacement isolation, reopened work and cancellation settlement.
- `account-routing`: account/model exclusions on reused WebSockets.

## Impact

Priority-check repository, observation store, OAuth singleflight waiting, usage updater, WebSocket request admission and focused regressions. No new setting, schema migration, UI change or production operation.
