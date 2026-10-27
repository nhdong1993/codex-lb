## Why

With about 3,000 accounts, `GET /api/dashboard/overview` takes about 6 s at p50 on production (HAProxy, 24 h) and returns about 518 KB gzipped. Every call rebuilds the weekly credit pace from usage history, which the Overview page and the status bar never show, and both pollers ask for it more often than account usage changes (usage refreshes every 60 s by default).

## What Changes

- `GET /api/dashboard/overview` accepts `weeklyPace=false` to skip the weekly credit pace; `weeklyCreditPace` is then `null`. The default stays `true`, so the Dashboard page and older clients are unchanged.
- The Overview page and the status bar request the overview with `weeklyPace=false`, and both poll it every 60 s instead of at the dashboard refresh interval (5–60 s, default 15 s).

## Impact

- Backend: `app/modules/dashboard/api.py`, `app/modules/dashboard/service.py`.
- Frontend: `features/dashboard/api.ts`, `features/dashboard/hooks/use-dashboard.ts`, `features/dashboard/components/dashboard-overview-page.tsx`, `components/layout/status-bar.tsx`.
- On `/dashboard` the status bar now makes its own overview call without weekly pace every 60 s instead of sharing the Dashboard page's call.
