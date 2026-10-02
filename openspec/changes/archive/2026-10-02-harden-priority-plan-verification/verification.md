# Verification: priority plan review fixes

This follow-up addresses the four reproduced findings from review of `confirm-plan-downgrades-promptly`. No production deployment, migration, account mutation, commit or push was performed. Unrelated workspace edits were preserved.

## Coverage

| Finding | Fix | Regression evidence |
| --- | --- | --- |
| Old evidence survives credential replacement | Account-row lock before reading enqueue/observation source guards; account-before-child order matches replacement. | PostgreSQL tests start stale enqueue/observe/clear while replacement holds its uncommitted transaction, verify the worker is actually blocked, then commit replacement and assert no stale work/evidence survives. A fresh Free sample counts as one. |
| Reused WebSocket bypasses account/model exclusion | Shared evidence checked at reuse and again after admission waits; existing socket-retirement and rejected-turn cleanup paths preserve ownership and accepted siblings. | Actual `/v1/responses` and `/backend-api/codex/responses` WebSocket routes cover movable turns; further cases cover conversation/file owners, accepted siblings, exclusion during admission, unrelated models and expiry. |
| Completed work swallows later Free evidence | Reopen only with remaining attempts, keeping the original deadline and scheduling after 15 seconds; new generation rejects stale completion. | Account-summary route reports pending again, then Free after confirmation. Tests assert unchanged attempt count/deadline, stale completion rejection, duplicate coalescing and no restart of exhausted work. |
| OAuth refresh outlives priority shutdown | Priority callers opt into draining shared OAuth exchange/persistence on cancellation; ordinary callers retain detach behavior. | Shutdown and timeout tests exercise real AuthManager singleflight with a second ordinary waiter, block during exchange and token persistence, and assert completion waits for saved rotated tokens, cancellation propagates and no shared refresh remains active. Existing auth unit tests cover ordinary cancellation. |

## Validation

- PostgreSQL 18 isolated integration suite: **28 passed**, including all three replacement-contention cases. The dedicated test container was removed afterwards.
- Auth/usage/observation/priority lifecycle/proxy transient regression slice: **276 passed**, with three PostgreSQL-only cases skipped on SQLite and covered in the PostgreSQL run.
- Expanded model-exclusion route cases: **8 passed**, including file ownership and expired evidence.
- Full direct WebSocket and account-availability suites: **174 passed**. The later file/expiry parameter additions are covered by the eight-case run above.
- Strict change validation and all **67 main specifications** passed; follow-up requirements and context are synced.
- Targeted Ruff lint/format and `git diff --check` passed. Proxy architecture, cancellation-safety and timing-seam checks passed without changing thresholds.
- Repository-wide `ty check` still reports the same two diagnostics outside this change: `tests/integration/test_proxy_chat_completions.py:109` and `tests/unit/test_key_dashboard_install.py:204`. No new diagnostic was introduced.

The broad WebSocket test fixture uses accounts that do not exist in the database and some fake upstreams emit response events before `send_text`. Its model-admission lookup is stubbed alongside its existing account-availability stub. Database-backed peer exclusion is tested separately in `test_proxy_websocket_account_availability.py`; those tests use the real shared evidence query.

One expanded route-test run emitted an aiosqlite thread teardown warning after passing. The affected unrelated/expired cases passed again with `PytestUnhandledThreadExceptionWarning` promoted to an error. The full WebSocket run passed with another aiosqlite teardown warning in its existing lite-replay test. These warnings are recorded rather than treated as proof of clean whole-process teardown. Starlette's existing BlockingPortal deprecation warning remains.

## Operational limits

Priority cancellation deliberately waits beyond its fetch timeout if an already-started shared OAuth exchange must persist a rotated token. It does not cancel that shared exchange or change permanent-error classification. Existing authentication exchange/persistence bounds still apply. New Free evidence reuses the original two-minute window and three-attempt budget, so exhausted/expired work remains subject to ordinary fleet refresh. No additional schema, setting, frontend build or visual change was required by these fixes.

All four review findings have implementation and regression coverage. No remaining requirement gap was found in this scoped verification; the unrelated typecheck diagnostics and test teardown warnings above remain documented limitations. All six tasks are complete and the change is ready to archive.

## Subsequent review

A later adversarial review reproduced three additional ordering/surface gaps: Free arriving before completion, closure during the final WebSocket query, and HTTP bridge reuse. See [the follow-up verification](../2026-10-02-close-plan-verification-review-gaps/verification.md) for fixes and expanded regression coverage. The earlier scoped assessment above did not cover those interleavings.
