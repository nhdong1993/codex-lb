## 1. Fix confirmed review findings

- [x] 1.1 Normalize raw driver failures at model admission; verify both routes, sanitized envelopes, resource release, sibling completion and cancellation.
- [x] 1.2 Preserve guarded goal restart selection for excluded cached/in-flight owners; verify actual sticky selection and hard-ownership controls.
- [x] 1.3 Fix independent review's direct WebSocket and cold-selection failure paths; verify sanitized errors, unsent cleanup, accepted sibling completion and retry on the same socket.
- [x] 1.4 Preserve confirmed Free evidence across token-rotation write conflicts; verify scheduler/API convergence within the remaining attempt budget and credential replacement fencing.
- [x] 1.5 Handle model-evidence failure during real cold WebSocket selection and allow retry on the same socket.
- [x] 1.6 Fence ordinary evidence clearing against credential replacement under the account lock; verify scheduler/API convergence and PostgreSQL contention.
- [x] 1.7 Fix final-review rotation races using a persisted replacement generation; cover paid reset, first-Free enqueue, unchanged-token replacement, migration/backfill and PostgreSQL contention without a fourth review iteration.

## 2. Independent review and verification

- [x] 2.1 Run Codex CLI adversarial review and fix verified in-scope findings, up to three iterations; save review results.
- [x] 2.2 Run mapped regression suites and repository lint/type/architecture checks; document any pre-existing failures separately.
- [x] 2.3 Sync requirements/context, pass strict OpenSpec validation, verify and archive the completed change.
