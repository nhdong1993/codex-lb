# Verification: backport-upstream-october-reliability

Originally verified against fork HEAD `67294897` plus the pre-existing dirty workspace on 2026-10-02. Re-verified on 2026-10-13 against HEAD `614cf5c2` plus the current dirty workspace after the review-defect fixes recorded under "Review-defect follow-up"; only the commands listed there were re-run at `614cf5c2`, and the "Test results" section remains the `67294897` baseline. This is a selective five-fix backport, not a release merge.

## Summary

| Dimension | Result |
| --- | --- |
| Completeness | 7/8 workflow tasks complete; all five implementation tasks and seven requirements covered; archive checkpoint remains open |
| Correctness | New regressions, broad routing tests, preservation tests and rebuilt-helper wire probes exercised |
| Coherence | Shared predicates and existing admission/settlement owners retained; no migrations, configuration additions or UI changes |

## Requirement and scenario evidence

| Requirement | Implementation | Coverage |
| --- | --- | --- |
| Patched native TLS | `Cargo.toml`, `Cargo.lock`: Rustls 0.23.45, webpki 0.103.15, aws-lc-rs 1.18.1, aws-lc-sys 0.45.0 | Packaging assertions, locked workspace Rust tests/build, native SSE/routed HTTP/WebSocket wire suites |
| Force Probe compatibility | `app/modules/accounts/service.py`: omit unsupported `max_output_tokens`, preserve gpt-5.5 default and warmup enrollment | `test_accounts_service_probe.py` and public dashboard endpoint `test_accounts_api_probe.py`: reject-if-field-present regression, status guards, missing accounts and refresh |
| Spendable secondary credits | `app/core/usage/quota.py` `has_usable_credits`: unlimited or positive balance only; `app/modules/accounts/mappers.py` RATE_LIMITED recovery delegates to the same predicate | `test_account_mappers.py`, `test_load_balancer.py`: missing/zero balances, both-window precedence, reset guards, disabled states, bare-flag RATE_LIMITED recovery |
| Credit-backed selection | Same shared quota helper, unchanged freshness and selection ownership | `test_load_balancer_multi_replica.py` and unit selection tests: newest credit evidence and peer recovery, no bare-flag override |
| Coalesced usage refresh | Shared predicate in stream health handling; existing `UsageUpdater.request_refresh` lane | `test_proxy_utils.py`: coded/code-less refresh, negative codes, debounce and absent scheduler; `test_usage_updater.py`: singleflight, freshness, independent session and eligibility |
| Retryable drain denial | `app/core/middleware/inflight.py`: existing HTTP-denial helper, 503, Retry-After: 5 | Middleware tests cover both proxy families including trailing slashes, generic paths, registration race, cancellation and pre-admitted connections; real Responses WebSocket routes cover terminal ownership and late admission |
| Code-less usage-limit terminals | `app/core/errors.py`, proxy classifier, streaming (including the owner-pinned `previous_response_id` rewrite) and WebSocket consumers | Foundation/utility tests plus public HTTP/WebSocket routes: wording normalization, explicit-code precedence, pre-visible retries, final account, post-visible health, unchanged terminal fields, ownership and settlement regressions; `test_codeless_usage_limit_routes.py`: owner-pinned rewrite parity, echoed `invalid_request_error`, keyed settlement-before-health |

## Review-defect follow-up (2026-10-13, HEAD `614cf5c2`)

Review of the uncommitted backport found two implementation defects and one coverage gap. Fixes are scoped to the files below; streaming `mixin.py`/`retry.py`, settings, model admission and load balancer were not edited.

- **D1 — owner-pinned code-less usage-limit frame (fixed).** `_rewrite_previous_response_stream_error` (`app/modules/proxy/_service/streaming/helpers.py`) rewrote a coded `usage_limit_reached` terminal on a `previous_response_id`-pinned HTTP stream to `previous_response_owner_unavailable`, but the code-less form (`upstream_error` + usage-limit wording) raised a retryable error, excluded the owner, failed selection closed and surfaced a fresh `upstream_error` with an account-less request log. The rewrite now applies `is_upstream_usage_limit_rejection` and records `usage_limit_reached` as the owner's health code, mirroring `_websocket_transparent_replay_error_code`. Red check: with the fix removed, the new code-less route case fails (`upstream_error` surfaced) while the coded case passes.
- **D2 — dashboard bare-credit recovery (fixed).** `app/modules/accounts/mappers.py` kept a private `_has_credit_override` that accepted a bare `credits_has`, so a RATE_LIMITED account was shown recovered while proxy selection ignored the flag. The mapper now calls the shared `app/core/usage/quota.py` `has_usable_credits` (renamed from the private `_has_usable_credits`; no behavior change in quota). Red check: the new bare-flag cases fail against the old predicate.
- **D3 — product-path coverage (added).** `tests/integration/test_codeless_usage_limit_routes.py` adds HTTP stream route tests for: owner-pinned coded/code-less parity (no sibling dispatch, `previous_response_owner_unavailable`, owner RATE_LIMITED, one usage refresh); an `invalid_request_error` quoting usage-limit wording as an HTTP 400 and as a terminal frame (surfaced unchanged, one attempt, no RATE_LIMITED, no refresh); and keyed API-key code-less usage-limit health for sibling retry, final account and after-visible output, asserting every reservation for the key is closed (`finalized`/`settled`/`released`) when the exhausted account's health write runs. No ordering bug was found. Red check: widening `_MESSAGE_CLASSIFIED_CODES` to include `invalid_request_error` fails both echoed-wording cases.

Commands run at `614cf5c2` (synthetic test databases, `CODEX_LB_ENV_FILE=/tmp/codex-lb-no-production-env`):

| Command | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1216 files already formatted |
| `uv run python scripts/check_proxy_architecture.py` | proxy architecture checks passed |
| `uv run pytest tests/integration/test_codeless_usage_limit_routes.py tests/unit/test_account_mappers.py tests/unit/test_failover_foundation.py tests/unit/test_graceful_shutdown.py tests/unit/test_accounts_service_probe.py tests/integration/test_accounts_api_probe.py -q` | **196 passed** |
| `uv run pytest tests/integration/test_proxy_websocket_responses.py -q -x --timeout=120` | **161 passed**, 1 existing Starlette/AnyIO deprecation warning, no timeout |
| `uv run pytest tests/unit/test_proxy_utils.py -q -k "previous_response or owner or usage_limit or rewrite"` | **260 passed**, 1150 deselected |
| `uv run pytest tests/integration/test_proxy_transient_retry.py tests/integration/test_proxy_responses.py -q -k "usage_limit or pinned or previous_response or owner"` | **23 passed**, 147 deselected |
| `git diff --check` on the edited source/test files | clean |

`openspec validate` was not re-run: the `openspec` CLI is not installed in this environment. The full-file WebSocket run above completed cleanly once; that is one clean observation, not a root-cause resolution of the earlier intermittent teardown warning.

## Test results

All Python suites used synthetic test databases with `CODEX_LB_ENV_FILE=/tmp/codex-lb-no-production-env` and `TMPDIR=/dev/shm`. No production account probes or quota-consuming requests were sent.

- Red baseline before implementation: **7 failed, 78 passed**, reproducing spendable-credit, drain denial and probe defects.
- Additional text-visible regression before the fork-specific adjustment: **3 failed, 3 passed**. Existing lifecycle-visible cases alone did not cover text-visible health suppression.
- Final focused suite: **1663 passed**. Account mapper, shutdown, probe service/route, failover foundation, proxy utilities, packaging and HTTP transient-retry files were run in full.
- Initial expanded routing run: **555 passed, 1 timeout**. The timeout was the existing oversized WebSocket request test, not a new quota/drain regression. It passed on the independent preservation run.
- Full WebSocket sequence rerun: **160 passed, 1 timeout**. This time the sequenced accepted-capacity test timed out in `TestClient.__exit__`, waiting for its AnyIO portal thread to close. The initial oversized test passed in this run. The two timeout tests then ran together independently: **2 passed in 2.34 seconds**. The file is not claimed as a clean full-suite pass; the intermittent teardown issue remains open.
- Preservation suite: **384 passed**, covering that timeout rerun, usage updater, source WebSocket guard, narrow overload isolation, native adapter, account import and OAuth flows. One existing Starlette/AnyIO deprecation warning remains.
- Native helper: `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, **26 Rust tests**, and locked release build all passed in a disposable Rust 1.96.0 build environment, limited to two compile jobs. The temporary extraction container was removed; production containers were not recreated.
- Native wire suite: **320 passed, no skips**, using the newly built helper via `CODEX_LB_NATIVE_EGRESS_TEST_BINARY`. Covers real local SSE, routed HTTP and WebSocket traffic, including failure/cancellation and byte-budget behavior.
- Ruff check and format check: **21 task Python files passed**. `git diff --check` passed.
- Change-specific OpenSpec strict validation passed. Canonical specs and context were synchronized for all four capabilities.

Results above are per-run counts, not a de-duplicated test total. Raw logs and JUnit reports are under `/tmp/codex-lb-october-backports.Oq5y1C` on this host.

## Fork adaptations and preservation

- Unlike the later upstream tree, this fork has additional health consumers. Upstream-authored messages are passed through the pre-visible stream gate, terminal/error retry branches and direct WebSocket finalizer. Proxy-authored terminal cleanup deliberately remains code-only.
- The existing text-visible guard still protects ordinary transient failures. Proven quota exhaustion alone now records health after visible text; route tests assert one upstream attempt, unchanged terminal code/message, and no duplicated text.
- The imported negative usage-refresh test stubs the fork's separate plan-verification scheduler. It still fails if `UsageUpdater.request_refresh` or the quota cleanup scheduler is called for a non-usage-limit error.
- Baseline-added lines were checked against current overlapping files: all **108 non-empty pre-existing added lines** remain present across account service, stream helper/retry and account-routing/usage-refresh spec/context files. Task-only diffs against the saved overlapping originals were reviewed.
- In particular, the narrow OpenAI-processing-message isolation predicate, `current_settlement.account_health_error` settlement-first guard and new-account warmup enrollment remain intact. Source ownership, UTC+7 reset/credit fields, API-key usage groups, existing native queues and unrelated dashboard changes were not replaced.
- No migration, Rust source, Python dependency manifest, release version or changelog was changed by this task. No commit, push, PR mutation or deployment was performed.

## Issues and limitations

**CRITICAL implementation findings:** none open. The 2026-10-02 pass missed D1 and D2 above; both are fixed with route/unit regressions in the 2026-10-13 follow-up. The final archive checkpoint is intentionally incomplete.

**WARNING — intermittent WebSocket teardown timeouts:** two full-suite attempts each timed out on a different existing test, while both tests passed when rerun together. The observed stack is blocked in TestClient/AnyIO portal shutdown, with an asyncio cancellation/SQLAlchemy cleanup trace. These results suggest teardown/order sensitivity but do not prove its root cause or establish that it predates this patch. Do not count either timed-out suite as wholly passing. Before calling the full WebSocket gate green, investigate task/session cleanup using the exact tests and logs above in a separate diagnostic step, then obtain a clean full-file run.

**WARNING — pre-existing canonical OpenSpec validation debt:** full `validate --specs --strict` reports **52 passed, 15 failed**. Comparison using the same strict validator against pre-task originals confirms the exact same 15 failing capabilities before and after, with **no newly failing capability**. The existing outbound-client errors are unchanged; usage-refresh loses one old parser error because the modified requirement now puts MUST on its first line. Unrelated normative-format cleanup belongs in a separate scoped documentation change. Details: `spec-validation.json` and `spec-baseline-comparison.jsonl` in the evidence directory.

**Limitations:** this is not a full repository test run, deployment smoke test, dependency-wide security audit, or GitHub PR-readiness verdict. Cloud CI, current-head review threads and mergeability gates were not requested or evaluated. Updating the lockfile does not patch the production helper until a later authorized deployment rebuilds it.

## Final assessment

The five selected backports are implemented and their targeted regressions pass. All seven requirements have implementation and regression evidence, and the four canonical capability specs/context are synchronized. Keep this change active: archive confirmation has not been received, and the broad WebSocket teardown warning is not resolved. Commit, push and production rollout remain outside this task's scope.
