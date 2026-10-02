## Implementation

- [x] 1. Serialize enqueue and observation writes with credential replacement; add PostgreSQL overlap regressions.
- [x] 2. Reopen completed verification for new Free evidence without extending deadline or resetting budget; add regression coverage.
- [x] 3. Enforce model exclusions on reused WebSocket turns; cover movable, pinned and accepted-sibling behavior.
- [x] 4. Drain OAuth refresh on worker cancellation/timeouts; test real singleflight and preserved ordinary cancellation semantics.

## Verification

- [x] 5. Run focused SQLite/PostgreSQL and routing/authentication suites, lint/type/architecture checks and strict OpenSpec validation.
- [x] 6. Sync stable specs/context, record verification and archive the completed change.
