# Post-implementation review loop — 2026-10-12

Scope: this change and `deny-http-only-source-websocket-upgrades`. The operator requested review and fixes until no actionable findings remained in these changes. Existing unrelated working-tree edits were preserved. No commit, push, deployment or production configuration mutation occurred during this review.

## Review outcome

Two completed independent Codex CLI reviews found no actionable defects in the scoped production diff. The first checked ownership, cap/budget selection, burst retention, no-replay behavior and source-only handshake policy. The second checked the final test-only corrections and their interaction with that original diff. Reviewers inspected code/tests but did not execute tests; the checks below were run by the implementation session. An earlier invocation could not read files due to its local sandbox failure and is **not** counted as a completed review.

The original production files did not change during this loop. The only Python corrections were two verification blockers already present when the review began:

| Finding | Correction | Status |
| --- | --- | --- |
| `tests/integration/test_proxy_chat_completions.py`: inferred generic error dictionary violates the typed `ProxyResponseError` envelope | Annotate the fixture error as `OpenAIErrorDetail` | Fixed and independently reviewed; uncommitted |
| `tests/unit/test_key_dashboard_install.py`: invariant nested list type is not assignable to `JsonValue` | Construct the equivalent JSON list at the assignment boundary | Fixed and independently reviewed; uncommitted |

These changes do not alter application behavior, specs, fixture JSON values or test assertions. No normative requirement changes were needed.

## Completed verification

Commands use the existing `.venv` executables. The four primary pytest groups are disjoint: **571 passed, 19 skipped** in total.

| Check | Result | Evidence file under the local review directory |
| --- | --- | --- |
| `pytest tests/unit/test_overload_backoff.py tests/integration/test_proxy_transient_retry.py tests/integration/test_load_balancer_multi_replica.py tests/unit/test_load_balancer_concurrency.py --timeout=45 --timeout-method=thread -vv --tb=short` | 284 passed in 355.34s | `broad-routing-round1.log` |
| Source handshake/native WS/review/input-discovery, installer catalog, transport fallback and required-capability exception group, listed below | 236 passed in 497.12s | `broad-source-round1.log` |
| `pytest tests/integration/test_proxy_chat_completions.py::test_openai_server_errors_escalate_only_with_recognized_message tests/unit/test_key_dashboard_install.py -q --timeout=40 --timeout-method=thread --tb=short` | 47 passed, 19 skipped in 98.83s | `type-regression-tests.log` |
| `pytest tests/integration/test_proxy_overload_soft_affinity.py --timeout=30 --timeout-method=thread -q --tb=short` | 4 passed in 11.85s | `public-soft-affinity-final.log` |
| `ruff check .` | Passed | `ruff-final.log` |
| `ruff format --check .` | Passed, 1214 files | `format-final.log` |
| `ty check` | Passed across the repository | `ty-final.log` |
| `openspec validate --specs --strict --json` using CLI 1.11.0 | 67/67 valid | `specs-final.json` |
| `git diff --check` | Passed | Terminal output |

The complete source group was:

```text
tests/integration/test_source_http_only_handshake.py
tests/integration/test_model_source_websocket.py
tests/integration/test_model_source_websocket_review.py
tests/integration/test_model_source_websocket_input_discovery.py
tests/integration/test_key_dashboard_install_catalog.py
tests/unit/test_websocket_transport_fallback.py
tests/integration/test_daybreak_capability_routes.py::test_websocket_transport_downgrade_never_applies_to_capability_handshakes
```

It ran with `--timeout=45 --timeout-method=thread -vv --tb=short`. All tests used their isolated test databases and stub providers, not production generation requests.

The earlier broad retry-suite progress/hang limitation recorded in `verification.md` is superseded by the completed **284-case** invocation above. The suspected case also passed alone, but no claim is made that the historical hang's root cause was established.

## Remaining environment/diagnostic limitations

- Nineteen Windows installer cases were skipped because PowerShell is unavailable; Windows execution is not claimed verified.
- The complete source suite emitted one Starlette/AnyIO deprecation warning, not a failed test.
- Two isolated invocations (the existing body-read disconnect case and the four new soft-affinity route cases) passed but emitted an intermittent aiosqlite worker-thread `Event loop is closed` teardown warning. A separate, temporary diagnostic observed an aiosqlite `Connection.__del__` stop future pending at test-loop closure. It did not establish which application path left that connection for finalization or attribute it to this patch. This diagnostic remains unresolved; no library monkeypatch, warning suppression or speculative production-lifecycle change was committed. The complete 284-case run did not emit that warning. The temporary diagnostic rerun is not included in the primary pass total.
- This is scoped local verification, not the complete repository test suite, cloud merge-gate verification or a production recovery claim.

Local evidence directory: `/tmp/codex-upstream-review-loop-kz0sx969`. It contains the task-only patch against saved pre-task baselines, final-review SHA-256 manifest, both independent verdicts, exact test logs and a preservation check. That check found only the two test files above changed relative to the start of this loop; review documentation was added afterwards.

Final assessment: no remaining actionable findings from the two independent reviews in the upstream-routing/HTTP-only production changes. Test-platform skips and the separate SQLite teardown diagnostic remain explicitly qualified above.

## Isolated commit verification — 2026-10-12

After the operator authorized commit, push and deployment, the staged changes were reconstructed on HEAD in a separate worktree, excluding unrelated pending work. That exposed a required pre-existing dependency: recognition of OpenAI processing-error messages and settlement-before-health-write ordering. Without it two new `server_error` affinity regressions failed. The minimal dependency and its existing `2026-09-16-count-openai-server-errors-for-isolation` artifacts are included; unrelated retry/model-plan changes remain excluded.

On the corrected isolated candidate:

- `pytest` for overload backoff, public soft-affinity routes, HTTP-only handshake, recognized processing errors and transient retry: **141 passed in 257.56s**. The previously documented intermittent SQLite worker teardown warning also occurred; it is not claimed resolved.
- Whole-tree Ruff check, Ruff format check (1205 files) and `ty check`: passed.
- OpenSpec 1.11.0 `validate --specs --strict --json`: **67/67 passed**.

Local evidence: `/tmp/codex-task-candidate-tests-v2.log`, `/tmp/codex-candidate-{ruff,format,ty}.log`, `/tmp/codex-candidate-specs.json`. The initial failing isolation run is retained as `/tmp/codex-task-candidate-tests.log`, not counted as successful verification.

Production already contains layered patches beyond the parent commit. Deployment therefore must inherit the exact live image `sha256:495aeb711817eb5528cb3eba8d552745dc8f7e9bc58cd8c81ff9c09dd753d6c7` and overlay only the six committed Python files. All six merge cleanly against the live source and match the isolated candidate byte-for-byte; three dependency files are already identical in production. This preserves prior releases without building the unrelated dirty tree. Production-overlay regression results and the authorized HA rollout outcome will be recorded in the release directory's deployment report; this pre-deployment addendum is not a claim that rollout has completed.
