# Proposal

## Why

Review reproduced two List regressions: Status overlaps Reset on narrow phones, and quota sort buttons no longer align with the quota windows underneath them.

## What Changes

- Wrap mobile Plan/Status/Reset metadata when there is insufficient room while retaining separate desktop columns.
- Present 5h/7d/Monthly sorting in an explicitly labeled group above the table. Give the quota data group a single descriptive column heading.
- Cover narrow phones, translated labels, quota display preferences and mixed paid/monthly-only rows in browser regressions.

## Capabilities

### Modified Capabilities

- `frontend-architecture`: responsive metadata and placement of quota sort controls.

## Impact

Frontend List layout, local translations and browser tests. No backend, sorting algorithm, API or database changes.
