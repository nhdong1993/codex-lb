## Why

Below the desktop breakpoint the APIs Detail view stacks the key selector above the detail panel. The selector is still a bounded internal scroller (`calc(100vh - 16rem)`, about 70% of a phone screen), so most page swipes land inside it and scroll the list instead of the page. Tapping a key then updates a detail panel that sits below the fold with no visible change, so operators cannot tell that the selection worked without hunting for the panel.

## What Changes

- Below the desktop breakpoint, the Detail-view key selector flows with the page instead of scrolling internally; at the desktop breakpoint it keeps its bounded scroll region.
- Below the desktop breakpoint, selecting a key in Detail view scrolls the detail panel into view below the sticky header. Desktop selection does not scroll the page.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-architecture`: APIs Detail view stays operable when the selector and detail panel are stacked.

## Impact

- Affected components: `frontend/src/features/apis/components/api-list.tsx`, `frontend/src/features/apis/components/apis-page.tsx`.
- Affected tests: APIs page component test and browser-smoke phone coverage.
- No API, schema, persistence or configuration changes.
