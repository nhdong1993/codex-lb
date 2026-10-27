# Context: lifetime API key limits

## Purpose

Give operators a hard, non-refilling budget per API key (for example "this contractor key may spend $50 total"), plus a dashboard button to start the counters over.

## Decisions

- **Far-future `reset_at` instead of a nullable column.** `api_key_limits.reset_at` and `api_key_usage_reservation_items.expected_reset_at` are `NOT NULL`, and reservation reserve/adjust/release use `reset_at = expected_reset_at` as a compare-and-set token. Keeping a datetime avoids touching every CAS path and response schema. Every automatic reset path filters on `reset_at < now`, so a far-future value is never selected.
- **The far-future value changes on every reset** (`9000-01-01 + (now - 1970-01-01)`). A constant sentinel would leave `reset_at` unchanged after a manual reset, so a reservation taken before the reset could still settle or release into the zeroed counter. Making it unique per reset keeps the existing fencing.
- **Lifetime is recognised by `limit_window`, never by the date.** The 429 message and the dashboard use the window value.
- **Backfill reads all history.** Adding a lifetime limit counts every retained successful request-log row for the key, consistent with "current window" backfill for periodic limits. Operators who want a fresh start press `Reset usage`.
- **Reset is whole-key.** The dashboard button sends the existing `PATCH /api/api-keys/{id}` `{resetUsage: true}`; periodic limits also start a new window, as that action already did. Per-limit reset was not requested.

## Constraints and failure modes

- Opt-in request-log retention may have pruned old rows; lifetime backfill then reflects only retained usage.
- `/v1/usage` reports the far-future `reset_at` string for lifetime limits. Clients should key off `limit_window == "lifetime"`.
- Rolling back to code without `lifetime` while lifetime rows exist fails enum validation on read: delete those rows first (`DELETE FROM api_key_limits WHERE limit_window = 'lifetime'`). PostgreSQL keeps the extra enum value, which is harmless.

## Example

1. Admin edits key `contractor`, adds rule Cost / `Lifetime (no reset)` / `$50`. The key already spent $12.34 last year, so the rule starts at `$12.34 / $50.00`.
2. Months later usage reaches $50: requests get `429` with message `API key cost_usd lifetime limit exceeded. Usage does not reset automatically.`
3. Admin clicks `Reset usage`, confirms; all counters return to 0 and the key works again.
