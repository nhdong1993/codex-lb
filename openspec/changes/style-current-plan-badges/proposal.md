## Why

The dashboard request-log grid and the account views color plan badges from one shared map. That map only knows `free`, `plus`, `team`, `pro`, `prolite` and `promax`. Every other plan falls back to the neutral Free style.

On 2026-10-19 production stored 7 `go` accounts, and 699 request logs in the last 7 days carried plan `go`. Those badges look identical to Free. The backend also recognizes `business`, `enterprise` and `edu` as account plans, and they get the same gray badge.

## What Changes

- Add dedicated badge styles for `go` (lime), `business` (blue), `enterprise` (indigo) and `edu` (teal) to the shared plan style map.
- `free` and unrecognized plan values keep the neutral style and their formatted label.
- Add a request-log grid regression test for the new styles and the neutral fallback.

## Capabilities

### Modified Capabilities

- `account-routing`: the plan badge requirement names every styled plan and the neutral fallback.

## Impact

- Frontend: `frontend/src/utils/plan-badge.ts` and the request-log table test. The request-log grid and the Accounts Detail, List and Grid views pick up the change through the shared helper.
- No backend, API, schema, migration or `CODEX_LB_*` setting change. Plan capacity and routing eligibility are unchanged.

## Non-goals

- Normalizing or renaming stored plan values such as `go`.
- Styling the plain-text plan labels in the dashboard account cards and list.
