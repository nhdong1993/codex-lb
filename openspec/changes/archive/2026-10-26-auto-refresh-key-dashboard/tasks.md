## 1. Tests

- [x] 1.1 Add integration tests for visible-only 30-second refresh, refresh on visibility return, later log page retention, background failure and 401, group chart retention, no overlap, manual supersede, and no Install refresh; verify they fail before the implementation.

## 2. Implementation

- [x] 2.1 Let `getKeyDashboardData` skip request logs; give `load` a silent mode and an in-flight guard; add the visible-only interval for the active tab.
- [x] 2.2 Reload the group panel from a reload signal behind a single owned request gate; keep data and show an alert on background failure.
- [x] 2.3 Track hidden chart members by name and masked prefix.

## 3. Specification and validation

- [x] 3.1 Sync the requirement into the main spec and context and mention auto refresh in `docs/api-keys.md`.
- [x] 3.2 Run key-dashboard tests, lint, build, and strict OpenSpec validation.
