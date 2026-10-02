## Why

Accounts that lose Plus can retain a paid deadline while the sequential fleet usage scan waits to confirm Free. Model entitlement errors do not accelerate that confirmation, while revoked credentials subsequently require a separate authentication repair.

## What Changes

- Add a bounded, shared priority check after an account/model rejection or the first eligible Free observation, preserving two independent usage observations and workspace ownership checks.
- Refresh the recorded subscription during priority verification and show a pending-plan label instead of a potentially stale countdown.
- Briefly exclude the rejected account/model pair without penalizing account health or breaking pinned ownership.
- Preserve existing guarded token refresh and explicit permanent-error reauthentication behavior; credential replacement discards old pending work.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `usage-refresh-policy`: bounded priority confirmation shared across replicas.
- `account-subscription-term`: pending verification presentation and prompt inactive-term checks.
- `account-routing`: temporary account/model exclusion on entitlement rejection.
- `database-migrations`: additive durable priority-check state and historical-row compatibility.

## Impact

Usage updater, account summaries, proxy error handling/selection, subscription refresh, background lifecycle, dashboard account views, and one additive migration. No new operator setting, dependency, production mutation, or deployment is required for implementation.
