## Why

On phones the API key edit dialog has three nested vertical scrollers: the dialog shell (made scrollable when the APIs List view landed) and the General and Limits columns, each capped at `55vh` with `overscroll-contain`. At 390x844 the stacked columns cover almost the whole dialog, so a swipe scrolls only the column under the finger and never reaches the dialog shell. The Save action starts below the fold and is effectively unreachable by touch. The create dialog already had this problem fixed with one internal scroll region and a persistent footer; the edit dialog was left out of that fix.

## What Changes

- Give the API key edit dialog the same viewport-bounded flex-column shell as the create dialog: persistent header and footer, one internal form scroller.
- Remove the two per-column `55vh` scroll constraints without changing fields, current-usage bars or submission behavior.
- Add browser-smoke regression coverage for the edit dialog at 320x568, 390x844 and desktop.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-architecture`: Require the API key edit dialog to keep its title, Close control and Save action inside compact viewports while every field stays reachable through one internal scroll region.

## Impact

- Affected dashboard component: `frontend/src/features/api-keys/components/api-key-edit-dialog.tsx`.
- Affected tests: `frontend/browser-smoke/dashboard.spec.ts`.
- No API, schema, persistence, dependency or configuration changes.
