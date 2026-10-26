## Why

The standalone API key dashboard loads its data only when the holder connects, clicks Refresh, or changes the request-log page. A dashboard left open shows stale usage, request logs, and group totals until the holder remembers to refresh, unlike the administrator dashboard, which refreshes itself.

## What Changes

- Refresh the open Overview or Group keys tab every 30 seconds while the browser tab is visible, and once immediately when the browser tab becomes visible again. The Install tab is never refreshed automatically.
- Automatic refreshes are silent: no spinner, current data stays on screen, and a non-401 failure keeps the data and shows an alert that clears after the next success. A 401 still disconnects.
- Overview refreshes the profile and usage on every tick, and request logs only while the first log page is shown, so a later page does not shift under the reader.
- Automatic refreshes never overlap a pending request; a manual Refresh, page change, or connect still runs and supersedes a pending automatic load.
- Group refreshes keep the chart's metric, table, and per-member visibility; member visibility follows the member, not its position.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-key-dashboard`: add automatic refresh of the active self-service tab.

## Impact

- Frontend only: `frontend/src/features/key-dashboard/` (page, group panel, daily chart, API helper) and its integration tests.
- No backend, API, schema, setting, or dependency changes.
