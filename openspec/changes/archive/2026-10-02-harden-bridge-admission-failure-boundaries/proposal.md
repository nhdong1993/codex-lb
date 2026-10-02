## Why

The latest review reproduced two remaining failures: an unwrapped asyncpg connection error still enters bridge send-failure cleanup, and model exclusion prevents a classified goal restart from reaching its guarded owner-replacement selection.

## What Changes

- Treat failures of the pre-dispatch model-evidence lookup as local admission failures, including raw driver/network errors, while propagating cancellation.
- Let a classified account-neutral goal restart reach guarded selection despite a cached owner's model exclusion, for both cached and in-flight sessions.
- Exercise the driver boundary and combined restart/exclusion product paths, then run the requested adversarial review/fix loop.
- Preserve confirmed Free evidence when concurrent routine token rotation rejects a guarded metadata write, so the remaining verification attempt can converge.
- Add a persisted credential generation that advances only on import/reauthentication; use it to fence evidence clearing and plan enqueue without treating routine token rotation as replacement.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `account-routing`: complete admission failure isolation and preserve classified restart selection.
- `usage-refresh-policy`: consume confirmed downgrade evidence only after the plan is successfully persisted.
- `database-migrations`: backfill credential generations without changing tokens or plan data.

## Impact

HTTP/WebSocket admission, account selection, plan verification and regression tests. A new account credential-generation column requires the standard migration before running the updated application. No new setting is introduced.
