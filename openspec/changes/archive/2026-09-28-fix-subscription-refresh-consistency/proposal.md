## Why

Review reproduced loss of a valid subscription term after routine token rotation, stale polling overwriting a manual refresh, and incorrect pending indicators when refreshing several accounts.

## What Changes

- Carry a valid subscription snapshot through successful token rotation for the same identity and plan, preserving the original check and attempt times.
- Cancel account reads still in flight before publishing a successful manual refresh.
- Derive pending subscription refresh accounts from all active mutations.
- Cover rotation, stale reads and concurrent success/failure with regression tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `account-subscription-term`: preserve verified terms across routine rotation and make manual refresh state consistent under concurrency.

## Impact

Account token persistence, account summary reads, frontend account queries and controls. No schema, API response, cadence or configuration changes.
