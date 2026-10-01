# Proposal

## Why

Operators scanning List view need to notice available reset credits that expire soon without opening every account.

## What Changes

- Show a small red dot above the Reset count when the nearest available credit expires within 72 hours.
- Keep the indicator current using the Accounts page clock and hide it for expired, unknown or unavailable credits.
- Preserve compact rows, reset visibility preferences and row selection.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-architecture`: List reset-count expiry indicator.

## Impact

Accounts List rendering, shared clock access, localized accessible text and frontend tests. Uses existing account summary fields; no API or schema changes.
