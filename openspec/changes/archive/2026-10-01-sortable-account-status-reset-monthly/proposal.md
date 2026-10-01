# Proposal

## Why

List view groups status and reset-credit counts with Plan, making fleet comparison difficult. Free accounts use monthly quota but cannot sort by its remaining percentage.

## What Changes

- Give Status and available Reset credits separate compact List columns with ascending/descending controls.
- Add Monthly remaining-quota sorting to desktop headers and the existing mobile sort menu.
- Preserve filtering, pagination, row actions, and reset-badge visibility preferences.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-architecture`: sortable Status and Reset columns and matching dropdown modes.
- `account-quota-presentation`: monthly remaining-quota sorting for Free accounts.

## Impact

Frontend account sorting, List layout, translations, and UI/browser tests. No API, database, dependency, or routing changes.
