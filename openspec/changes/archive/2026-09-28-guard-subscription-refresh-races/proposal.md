## Why

Review reproduced a first subscription snapshot becoming unusable when committed between token rotation's read and write. A delayed manual refresh can also attach a Plus deadline to an account already observed as Free.

## What Changes

- Evaluate snapshot validity at the atomic token update, including snapshots committed after the source read.
- Accept frontend subscription responses only for the current account source and when they do not supersede newer metadata.
- Add deterministic database interleaving, delayed-response and browser regressions.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `account-subscription-term`: preserve concurrently saved snapshots across rotation and reject manual responses for superseded sources or check times.

## Impact

Account token persistence and account-list cache updates. No schema, endpoint, deployment, cadence or settings changes.
