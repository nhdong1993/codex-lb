## Why

During the October 12 incident, repeated upstream overload and processing errors left soft-affinity requests returning to a failing account until the third backoff trip. Three qualified failures already establish sustained rejection; waiting for isolation prolongs client retries despite available siblings.

## What Changes

- Rebind movable soft affinity once the existing sustained-overload backoff trips, using the existing eligible replacement selection and cap checks.
- Keep single-failure and code-less burst cooldown behavior, hard owners, quota settlement, replica-local state and replay limits unchanged.
- Verify the externally failing HTTP route with repeated upstream failures and interleaved successes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `account-routing`: sustained overload backoff can release soft affinity before isolation.
- `sticky-session-operations`: preserve replacement eligibility, cap and hard-owner protections during earlier rerouting.

## Impact

Private load-balancer selection helpers, regression tests and OpenSpec. No new setting, migration, upstream replay, commit or deployment.
