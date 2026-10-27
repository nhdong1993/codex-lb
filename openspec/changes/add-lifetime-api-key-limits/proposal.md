## Why

Operators want an API key budget that never refills: a total number of tokens or dollars a key may spend over its whole life. Every existing limit window (`daily`, `weekly`, `monthly`, `5h`, `7d`) resets automatically. Operators also have no dashboard control to clear a key's counters, although `PATCH /api/api-keys/{id}` already accepts `resetUsage`.

## What Changes

- Add the `lifetime` limit window. A lifetime limit accumulates usage and is never reset by the lazy on-read reset or the hourly fallback sweep.
- Adding a lifetime limit to a key backfills its `current_value` from all retained successful request-log usage.
- A lifetime limit that is exceeded returns the usual `429 rate_limit_exceeded`, stating that usage does not reset automatically instead of a reset time.
- The dashboard edit dialog offers the `Lifetime (no reset)` window and a confirmed `Reset usage` action that sends the existing `resetUsage: true` update.
- PostgreSQL migration adds `lifetime` to the `limit_window` enum.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `api-keys`: new lifetime limit window and a dashboard control for the existing explicit usage reset.

## Impact

- Code: `app/db/models.py`, `app/modules/api_keys/{limit_windows,schemas,service}.py`, proxy 429 message builders, dashboard API key components and locales.
- Schema: one Alembic revision adding an enum value on PostgreSQL (no-op on SQLite). No new settings.
- API: `limitWindow` accepts and returns `lifetime` on `/api/api-keys` and `/v1/usage`.
