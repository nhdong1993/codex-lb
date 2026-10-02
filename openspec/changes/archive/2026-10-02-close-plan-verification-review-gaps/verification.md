# Verification: remaining priority-plan review gaps

All three reproduced findings have fixes and product-path regression coverage. This work made no production changes, deployment, commit or push. Other workspace changes were preserved.

## Requirement coverage

| Requirement | Implementation | Regression evidence |
| --- | --- | --- |
| New Free evidence survives in-flight paid completion | Independent first Free samples advance the existing generation for pending as well as completed work. The priority worker does not enqueue its own sample. Original request time and attempts remain unchanged. | `test_priority_plan_check_lifecycle.py` injects Free between a paid result and completion, reads the account-summary API as pending, and confirms Free with the next sample. A separate case proves the worker keeps its own generation and delayed retry. Both pass on SQLite and PostgreSQL. |
| Asynchronous model admission preserves unsent ownership | The direct WebSocket model lookup precedes the reconnect latch check and existing unsent handoff. | `test_proxy_websocket_account_availability.py` closes the upstream during the final model lookup on both public and backend routes. The next turn completes on a fresh socket, never sends to the retired socket, consumes no replay budget, releases account admission leases and records no health penalty. |
| HTTP bridge respects shared rejection | Cached candidates are checked before registry reuse, in-flight-created candidates are checked after waiting, and the final submit check uses pre-dispatch cleanup. Small pure reuse operations are factored out without increasing the architecture threshold. | `test_http_bridge_model_exclusion.py` covers both routes, movable/conversation/file ownership, unrelated and expired evidence, plus late exclusion and cancellation during lookup. An accepted sibling completes while the unsent request releases its real API-key reservation and admission resources. |

## Executed validation

- Direct WebSocket, availability, priority checks/lifecycle and usage updater: **345 passed, 3 skipped**. The skipped PostgreSQL MVCC cases passed in the dedicated PostgreSQL run.
- HTTP bridge integration, model exclusion, bridge unit/cancellation/idle lease suites: **1,298 passed**. This run began before the final pure reuse-helper extraction and extra cancellation parameter; the final code was separately checked by **27 reuse/recovery/parallel unit tests** and all **10 model-exclusion integration cases**.
- PostgreSQL 18 priority lifecycle and priority checks: **25 passed**. The isolated test container was removed.
- New regression cases: **14 passed** across the focused runs (two priority, two socket-close routes, ten bridge cases). Additional socket assertions for zero replay consumption and released leases passed on both routes.
- Ruff lint and format on all nine touched Python files, scoped typecheck, `git diff --check`, proxy architecture, cancellation safety and timing-seam checks passed. No architecture threshold was changed.
- Strict change validation and **67 main specs** passed. Delta requirements and stable context are synced.

## Limits and remaining diagnostics

Repository-wide `ty check` still reports the same two out-of-scope diagnostics at `tests/integration/test_proxy_chat_completions.py:109` and `tests/unit/test_key_dashboard_install.py:204`; scoped checking of every Python file changed here passes.

The broad WebSocket/usage run emitted Starlette's BlockingPortal deprecation warning and three aiosqlite thread teardown warnings involving a closed event loop. The dedicated bridge runs and PostgreSQL run passed without these warnings. The broad run is not evidence of warning-free teardown. No UI or schema change required frontend or migration revalidation in this follow-up.

The original two-minute window and three-attempt budget remain binding. Bridge evidence reads add database latency. No additional requirement gap was found in this scoped verification; the diagnostics above remain documented limitations.
