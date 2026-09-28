## 1. Atomic snapshot transfer

- [x] 1.1 Add deterministic late-save and concurrent replacement regressions checked through dashboard list/summary routes; confirm the late-save test fails before the fix.
- [x] 1.2 Move snapshot validity into the token SQL update and verify new regressions plus existing token CAS tests pass.

## 2. Frontend response ownership

- [x] 2.1 Add delayed-response hook tests for changed source, newer timestamps and matching subscription-only merges; confirm changed-source cases fail before the fix.
- [x] 2.2 Guard cache merges using current source and freshness; verify hook tests and browser Plan-change regression with before/after evidence.

## 3. Integration verification

- [x] 3.1 Run focused backend/frontend suites, lint/type checks, production build and browser tests.
- [x] 3.2 Synchronize main specs/context, validate strictly, record verification and archive the verified change.
