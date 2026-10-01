# Verification

## Completeness and correctness

All four tasks are complete. The added frontend requirement is synced to the main specification, and stable rationale is in frontend-architecture/context.md.

- Focused component checks: 45 tests across List overview, sorting and subscriptions passed across the initial run and the corrected List test rerun (23/23). The initial invalid-date fixture was rejected by the fixture schema before reaching the UI; the final test injects that invalid value after creating valid fixture data.
- Browser checks: five affected scenarios passed across the initial run and the final indicator test rerun. Initial browser failure was an overly specific computed border-radius assertion; the actual rendered dot is circular. Final checks cover dot position, unchanged row height, no overflow and pointer activation at 1440px and 320px, plus List management and three-language badge layout regressions.
- Production TypeScript and Vite build passed during browser setup.
- Scoped ESLint and git diff --check passed.
- Strict change validation passed; strict main specification validation passed all 67 specs.

## Coherence

The indicator uses the existing summary deadline and shared minute clock with no new timer per row or extra network request. Expired, missing and invalid deadlines do not qualify; the 72-hour boundary is inclusive. Positive counts, badge visibility, changed counts and minute transitions are covered at the rendered component path. Subscription clock behavior retains its existing tests.

## Screenshots

Synthetic fixtures show otherwise identical rows outside and inside the warning interval.

- Desktop: [without warning](evidence/before/list-1440.png) / [with warning](evidence/after/list-1440.png)
- Mobile: [without warning](evidence/before/list-320.png) / [with warning](evidence/after/list-320.png)

No outstanding implementation findings. No deployment performed.
