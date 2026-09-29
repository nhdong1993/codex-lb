# Proposal

## Why

The installer currently disables provider WebSockets whenever any catalog model prefers HTTP, including keys assigned both native accounts and model sources. Catalog preferences cannot identify source-only assignments because native metadata may still appear for those keys.

## What Changes

- Derive the exported provider transport flag from the authenticated key's assignments.
- Disable WebSockets only for keys with assigned model sources and no assigned accounts; keep them enabled for mixed, account-only, and unassigned keys.
- Preserve catalog refresh and model metadata on macOS, Linux, and Windows.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-key-dashboard`: Installer provider WebSocket policy follows key assignments at export instead of catalog preferences.

## Impact

Changes are confined to installer export/rendering, focused tests, and the owning OpenSpec capability. No new settings, dependencies, migrations, or dashboard layout changes are required. A newly exported installer is needed after assignment changes.
