## 1. Implementation

- [x] 1.1 Add the `weeklyPace` query parameter to `GET /api/dashboard/overview` and skip the history load, trailing demand, pace build, and API-key attribution in `DashboardService.get_overview` when it is false.
- [x] 1.2 Add `weeklyPace` to `getDashboardOverview`; give `useDashboard` a `weeklyPace` option with its own query key and 60 s polling; use it on the Overview page and in the status bar.

## 2. Tests

- [x] 2.1 Integration test: `weeklyPace=false` returns `weeklyCreditPace: null` and the same accounts and summary as the default call.
- [x] 2.2 Frontend tests: the Overview page requests `weeklyPace=false`; the option uses its own query key and polls every 60 s at a 15 s refresh setting; the status bar requests `weeklyPace=false`.

## 3. Verification

- [x] 3.1 Measure `get_overview` with and without weekly pace on a local Postgres seeded with 3,000 accounts and record the numbers in `context.md`.
- [x] 3.2 Run backend tests for the dashboard, frontend tests, lint, typecheck, and build; run `openspec validate lighten-dashboard-overview-polling --strict`.
