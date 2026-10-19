## 1. Specification

- [x] 1.1 Write proposal, context and the `account-routing` delta; run `openspec validate style-current-plan-badges --strict`.

## 2. Dashboard

- [x] 2.1 Add `go`, `business`, `enterprise` and `edu` styles to the shared plan badge map.

## 3. Tests

- [x] 3.1 Request-log grid test: each new plan gets its own style; an unrecognized plan keeps the neutral style. Confirm it fails without the map change.
- [x] 3.2 Run the targeted vitest files, `tsc -b` and eslint; capture a before/after screenshot of the Plan column.
