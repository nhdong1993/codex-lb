# Verification

## Scope and implementation

This change closes the latest model-admission and guarded goal-restart findings, plus confirmed in-scope defects from the requested `codex-review-loop`. The uncommitted workspace also contains unrelated work; it was not included in this fix scope. No production deployment or Git publication was performed. The repository Git workflow requires an explicit commit request, so the skill's per-finding commits were not created. Finding status `fixed` in this change means implemented and regression-verified in the working tree.

| Requirement | Implementation | Product-path regression |
| --- | --- | --- |
| Driver-independent admission isolation | Shared `proxy/model_admission.py`, balancer and both transports | `test_http_bridge_model_exclusion.py`: late admission, cache lookup, cold selection; real SQLAlchemy async connector boundary; reservations, sibling completion and cancellation |
| Direct WebSocket isolation | First lookup catches a normalized error as an unsent-turn rejection; final lookup uses existing request-local handling | `test_proxy_websocket_account_availability.py`: both routes, first/final query, wrapped/raw driver failures, reservation/gate cleanup, accepted sibling completion and same-socket retry |
| Initial direct WebSocket admission | Real selector converts normalized errors through the existing connect-failure emitter/sentinel | `test_proxy_websocket_account_availability.py`: both real routes, rejected unsent turn, reservation release and same-socket retry |
| Ordinary consumption fencing | DB evidence clear takes the account lock, then checks replacement generation, installation identity and any check generation guard | `test_priority_plan_check_lifecycle.py`: replacement evidence survives old clear; two transient failures followed by final-attempt confirmation; PostgreSQL lock contention |
| Guarded goal restart | Shared required-owner predicate defers classified restarts to existing guarded sticky selection | `test_http_responses_bridge.py`: cached/in-flight excluded quota owner with admitted predecessor; `test_http_bridge_model_exclusion.py`: active-owner, previous-response and file controls |
| Confirmation survives rotation conflict | `usage/updater.py` clears agreeing Free observations only after metadata sync succeeds | `test_priority_plan_check_lifecycle.py`: actual scheduler/API confirms Free on remaining attempt; replacement clears stale evidence/check and preserves new credentials |

## Independent review

Iteration 1: the independent Codex CLI review reproduced the direct WebSocket error-envelope access defect (P1) and a lost Free confirmation after token rotation (P2). Its earlier product-path probes also demonstrated cold-selection and direct-socket lookup failures. All were fixed. Raw final output is in `review-iteration-1.md`; deduplicated structured findings are in `review-findings.json`.

Iteration 2: two P2 findings were reproduced and fixed: cold real WebSocket selection escaped request-local error handling, and ordinary evidence clearing could delete replacement evidence. Raw output is in `review-iteration-2.md`. Seven focused product-path regressions passed.

Iteration 3: two P2 rotation races were reproduced: paid reset retained contradicted Free evidence, and first-Free enqueue could be suppressed. Raw output is in `review-iteration-3.md`. Both were fixed with a persisted replacement generation and regression coverage. The skill limits review to three iterations, so the final generation fix has local regression/static validation but **has not received a fourth independent review**. No known finding is intentionally left unresolved.

## Validation

- Broad mapped baseline after the initial driver/restart fixes: **1,606 passed, 7 skipped**. Includes bridge unit/integration suites, sticky routing, usage refresh and priority checks. The skips are PostgreSQL-only contention cases.
- Usage/evidence suites after the rotation fix: **185 passed, 7 skipped** on SQLite.
- PostgreSQL after iteration-1 fixes: **77 passed**, covering priority checks/lifecycle (including the seven MVCC cases) and HTTP bridge model exclusion.
- Load-balancer unit suites after adopting the shared admission boundary: **456 passed**.
- Direct WebSocket cancellation cleanup: **3 passed**.
- PostgreSQL after iteration-2 fixes: **34 passed**, including ordinary clearing blocked behind replacement.
- Final usage, priority lifecycle and both WebSocket suites after iteration-2 fixes: **384 passed, 8 skipped** on SQLite; all eight PostgreSQL-only cases passed in the 34-test PostgreSQL run. The final combined run emitted only one Starlette deprecation warning.
- Final HTTP/direct-WebSocket route suite: **84 passed**.
- Existing WebSocket response integration suite: **155 passed**.
- Repository Ruff check and format check: passed.
- Type check of the changed production code and mapped tests: passed.
- Proxy architecture check and `git diff --check`: passed.
- Strict change validation: passed. Strict main-spec validation: **67 passed, 0 failed**.

An earlier local run used an incorrect expected error for the active-owner control; the actual documented response is `503 hard_affinity_saturated`. The test now bounds the bridge budget and asserts that exact envelope, no owner transfer and no sticky abandonment. Another route run was interrupted during an existing cancellation-cleanup test after 81 passes; the cleanup cases passed in isolation, and the final route suite then passed with a bounded timeout. The existing WebSocket fake fixture was updated to stub the new shared helper instead of the removed module import.

## Limits

Full-repository `ty check` still reports two pre-existing errors outside this fix scope: `tests/integration/test_proxy_chat_completions.py:109` and `tests/unit/test_key_dashboard_install.py:204`. SQLite route runs emitted existing teardown warnings about aiosqlite worker threads targeting closed event loops. The full repository test suite and cloud PR gates were not run; this is scoped local verification, not PR merge approval. The isolated PostgreSQL test container is used only for test databases and is stopped at completion.

A rotation conflict on the final allowed check still falls back to ordinary fleet refresh. Retained evidence does not reset the original attempt budget or create extra authentication attempts.

## Final generation fix verification

The additive migration follows `20261002_000000_add_account_plan_checks` and preserves historical token, plan and status values while backfilling generation zero. Import/reauth increments it in the same transaction as replacement/evidence invalidation; rotation preserves it. Installation identity additionally fences delete/recreate of the same local account ID. Fingerprints include the generation, conservatively restarting evidence from the old format.

- New paid-reset ordinary/priority and first-Free enqueue rotation/replacement regressions: passed in the lifecycle suite.
- SQLite migration plus lifecycle: **15 passed, 8 skipped** (PostgreSQL-only cases).
- PostgreSQL migration/backfill/downgrade/re-upgrade: **1 passed**.
- Final usage/evidence, priority checks/lifecycle and migration suite: **191 passed, 8 skipped** on SQLite.
- Final priority checks/lifecycle on PostgreSQL: **38 passed**, including the eight contention cases.
- Repository lock tests: **17 passed** after correcting the asynchronous mocks.
- Final PostgreSQL lineage suite including delete/recreate identity fencing: **23 passed**.
- Final SQLite priority/lineage rerun: **31 passed, 8 skipped**, with the eight PostgreSQL cases covered above.

An expanded OAuth run hit one polling deadline while other database suites ran concurrently; all four device-reauth variants passed on isolated rerun. The priority replacement fixture was updated to simulate generation advancement at replacement. Two repository lock tests had synchronous mocks for the existing asynchronous scalar read; they now use AsyncMock while retaining their lock-order assertions. There is no production code change to routine rotation for those fixtures.

The updated application requires the new migration. Generation fencing assumes replacement operations are performed by updated replicas; an old replica does not increment this new field. No deployment or cloud merge checks are included.

## Completion assessment

Completeness: all scoped findings are implemented and all added requirement scenarios have product-path or migration regression coverage. Main specs and context are synced. Correctness: driver errors remain request-local across cold/reused HTTP and WebSocket paths; restart ownership controls remain enforced; rotation and replacement have distinct persisted identities; SQLite/PostgreSQL tests confirm convergence and replacement fencing. Coherence: shared admission normalization is outside dispatch, replacement generation advances at the existing transaction boundary, and no new user setting was added.

An optional wider legacy migration/unit run was interrupted after its already-loaded repository fixtures reported the two mock errors described above; that run is not counted as a successful full suite. The corrected repository suite passed separately, and the new migration passed dedicated SQLite and PostgreSQL round trips. No known scoped regression remains. Full-repository type checking retains the two unrelated diagnostics listed above. No fourth independent review was run after the final generation fix.

## Commit preparation verification

After the user requested a commit, only plan-verification changes and their prerequisites were staged. Mixed warm-up, API-list, overload and model-catalog work was left unstaged. A separate checkout exported from the Git index verified the proposed commit independently of that work: 32 backend regressions passed (8 PostgreSQL-only skips already verified above), 17 frontend tests passed, and scoped type, Ruff, architecture and all 67 strict spec checks passed.

Five older migration tests were updated to the credential-generation head. The reset-credit migration fixture previously used the current Account ORM against its historical schema; it now seeds only historical columns explicitly. Five migration tests passed on the first pass; the corrected reset-credit test passed on rerun, covering all six selected migration suites.
