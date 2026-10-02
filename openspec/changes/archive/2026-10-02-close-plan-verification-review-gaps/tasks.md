## 1. Implementation

- [x] 1.1 Fence in-flight paid completion against newer Free evidence; verify account-summary regression and own-worker retry behavior.
- [x] 1.2 Recheck direct WebSocket retirement after model admission; verify a coordinated close reconnects the unsent turn without health penalties.
- [x] 1.3 Enforce bridge model exclusion during reuse and dispatch; verify movable/pinned routes, admission races, sibling completion and resource cleanup.

## 2. Verification

- [x] 2.1 Run relevant SQLite/PostgreSQL, transport and usage regression suites plus lint/type/architecture checks; record actual results.
- [x] 2.2 Sync requirements and context, run strict OpenSpec validation, and archive only after verification.
