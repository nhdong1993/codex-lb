## Why

Operators running hundreds of accounts cannot read pool health from the Accounts list, which shows one card per account. They need status and quota at a glance, split by plan, on a surface that stays legible as the pool grows.

## What Changes

- A read-only Accounts overview at `/accounts/overview`, reached through "List | Overview" tabs on the Accounts pages.
- One row for all plans, then one row per plan, each with a status breakdown and a 10-bucket remaining-quota histogram per window (5-hour, weekly, monthly).
- Regression coverage and before/after dashboard evidence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-architecture`: Accounts plan overview.

## Impact

Frontend only. Reuses `GET /api/accounts` and the existing accounts list query. No backend, API, schema, migration, setting, dependency, or navigation item changes.
