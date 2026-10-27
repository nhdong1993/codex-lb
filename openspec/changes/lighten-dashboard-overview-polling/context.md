# Context

## Why the Overview page was expensive

Production (dong01, about 3,000 accounts, HAProxy log over 24 h on 2026-10-27):

| Endpoint | Calls | p50 | p90 | Size (gzip) |
|---|---|---|---|---|
| `/api/dashboard/overview?timeframe=7d` | 691 | 5.9 s | 10.4 s | ~518 KB |
| `/api/dashboard/projections` | 736 | 3.5 s | 8.5 s | 1 KB |

`DashboardService.get_overview` has no response cache. Each call rebuilds the account summaries, the request-log aggregates, and the weekly credit pace (usage history for every account, trailing demand, API-key attribution). The Overview page polled it at the dashboard refresh interval (default 15 s), and the status bar polled the same full response every 60 s on every page only to read `lastSyncAt`. Account usage itself refreshes every 60 s (`usage_refresh_interval_seconds`).

## Decisions

- `weeklyPace` is an opt-out query parameter with default `true`, so the Dashboard page, older SPA bundles, and external callers keep the current response.
- The Overview page and the status bar use one `useDashboard(timeframe, { weeklyPace: false })` query under its own key (`["dashboard", "overview", timeframe, "without-weekly-pace"]`). A separate key keeps a response without `weeklyCreditPace` out of the Dashboard page's cache. Prefix invalidation of `["dashboard", "overview"]` still reaches it.
- The Overview page builds its cards with `buildDashboardView(..., { weeklyPace: false })`, so a deliberately missing pace does not trigger the browser-side weekly pace projection meant for older backends (about 0.9 s of main-thread time per render at 3,000 accounts, found in review).
- The lighter query polls every 60 s. The dashboard refresh setting only offers 5, 15, 30, or 60 s, so a fixed 60 s is never faster than the setting.
- The response still carries every account. A summary endpoint without the account list was left out: the page still needs per-account data for plans with at most 100 accounts and account labels in the request table.

## Trade-offs

- On `/dashboard` the status bar no longer shares the Dashboard page's call; it makes one call without weekly pace every 60 s.
- The page and the status bar each run their own 60 s timer on the shared query, so the Overview can make up to two calls per minute, both without weekly pace.

## Measurement

Local Postgres 16, 3,000 accounts (2,500 free, 400 plus, 100 pro), 1,032,000 `usage_history` rows (7 days sparse plus the last 3 hours every 5 minutes, both windows), 100,000 `request_logs` over 14 days. `get_overview("7d")` timed in-process, six calls per run (first call cold, median of the other five), JSON from `model_dump_json(by_alias=True)`:

| Mode | Cold | Warm median | Raw JSON | Gzip |
|---|---|---|---|---|
| Before (current code, weekly pace) | 15.6 s | 1.87 s | 4,139 KB | 274 KB |
| `weeklyPace=false` | 0.60 s | 0.53 s | 3,944 KB | 242 KB |

Per open Overview tab: before, about 4 full calls per minute (≈7.5 s of server time per minute locally); after, at most 2 calls without weekly pace (≈1 s per minute). The browser still parses about 4 MB of JSON per call, but at most twice a minute instead of four or five times.
