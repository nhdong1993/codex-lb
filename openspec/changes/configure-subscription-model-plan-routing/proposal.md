# Configure subscription model Plan routing

## Why

Operators need to restrict selected subscription models to Free accounts while preserving existing selection for every unconfigured model and keeping model-source routing independent.

## What Changes

- Persist an optional exact-model-to-plan mapping in dashboard settings, empty by default.
- Allow explicitly configuring `gpt-5.6-terra`, `gpt-5.6-luna`, and `gpt-6-luna` for `free`; do not seed or apply those examples automatically.
- Apply configured plans as an additional eligibility restriction before existing ranking and failover.
- Preserve source routing, account ownership, API-key account scope, entitlement checks, and existing behavior for unconfigured models.

## Impact

Account-routing settings, database migration, subscription account selection, connection reuse, settings UI, and corresponding regression tests. The model catalog continues to describe upstream capabilities rather than operator routing policy.
