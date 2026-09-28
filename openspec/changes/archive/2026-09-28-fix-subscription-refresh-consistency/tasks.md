## 1. Regression coverage

- [x] 1.1 Reproduce snapshot loss through token rotation and dashboard reads, retaining replacement/CAS protections.
- [x] 1.2 Reproduce stale polling and concurrent refresh pending states through frontend hooks and controls.

## 2. Implementation

- [x] 2.1 Transfer matching subscription binding atomically during same-identity token rotation.
- [x] 2.2 Cancel stale list reads before publishing manual refresh results.
- [x] 2.3 Track pending refreshes per account across List, Grid and selected Detail.

## 3. Verification

- [x] 3.1 Run focused tests, auth persistence regressions, lint/type checks and frontend build; capture pending UI evidence.
- [x] 3.2 Sync normative requirements and context, validate strictly, verify implementation and archive the change.
