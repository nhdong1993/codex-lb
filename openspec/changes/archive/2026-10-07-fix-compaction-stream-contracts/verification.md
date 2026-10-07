# Verification: fix-compaction-stream-contracts

Local validation on 2026-10-07, following the three P2 findings from the
`codex-review-loop` review. No production traffic, deployment, restart, commit,
credential or global configuration changes are included.

## Corrections and evidence

1. Initial compact selection and the disabled-source probe now require
   streaming. The two compact routes select the same normalized streaming model
   as their equivalent terminal-trigger routes; disabled fallback is denied
   before reservation or upstream calls.
2. The bounded compact collector reuses the Responses event usage extractor and
   retains only scalar usage, reconstructing the typed usage envelope when
   terminal response usage is absent/null. Terminal usage retains precedence;
   malformed or negative present usage is not replaced with earlier counters.
   JSON, reservation and request-log assertions cover normal and >1MiB events,
   cached and reasoning counts and terminal precedence.
3. Pydantic validation failures from terminal error translation become HTTP 502
   `invalid_upstream_response`, with upstream status 200, one attempt, an error
   log, released quota and zero admission. Existing nested malformed envelopes
   that already translate to generic `upstream_error` remain upstream errors.
   Cancellation handling is unchanged.

## Checks

- The review's original temporary fixture reproductions: **8 passed** in 8.95s.
  Script: `/tmp/compaction-readonly-review/test_review_gaps.py`; result:
  `/tmp/compaction-stream-contracts-original-repros.log`.
- Permanent focused regressions: **30 passed, 111 deselected** in 30.79s:
  `TMPDIR=/dev/shm uv run pytest -q tests/integration/test_model_source_compaction.py
  -k 'selects_streaming_model or preserves_observed_usage or does_not_mask_invalid
  or malformed_error_is' --timeout=45 --maxfail=3`.
- Full compact/source compact/trigger/API-key suite before the membership guard:
  **371 passed** in 360.48s. The final suite including eight guard cases:
  **379 passed** in 359.64s using
  `TMPDIR=/dev/shm uv run pytest -q tests/integration/test_model_source_compaction.py
  tests/integration/test_proxy_compact.py tests/integration/test_proxy_compact_triggers.py
  tests/integration/test_api_keys_api.py --timeout=45 --maxfail=2`.
- Related source pool/dispatch/policy/replay/forwarding/unit dispatch suite:
  **517 passed** in 92.22s using
  `TMPDIR=/dev/shm uv run pytest -q tests/integration/test_model_source_pool.py
  tests/integration/test_model_source_dispatch.py tests/unit/test_request_policy.py
  tests/unit/test_replay_safety_portability.py tests/unit/test_model_sources_forwarding.py
  tests/unit/test_source_dispatch.py --timeout=45 --maxfail=3`.
- Ruff check/format and `uv run ty check` on the three changed Python files: passed.
- Proxy timing seam and cancellation safety checks: passed.
- `git diff --check`: passed.
- Strict change validation: passed. After sync/archive,
  `openspec validate --specs --strict --no-interactive`: **67 passed, 0 failed**.
- First Codex CLI re-review confirmed all three original fixes, then reproduced
  one new selection-miss regression: non-streaming-only source models fell
  through to subscription. The correction now checks source membership after
  streaming selection misses, retaining source-busy/disabled denials while
  respecting explicit subscription continuity. Eight permanent regressions
  cover both endpoints, enabled/disabled sources and subscription ownership.
  Final scoped CLI review returned **no actionable findings**, concluding the
  guard preserves source membership, alias fallback, subscription ownership and
  selection policy, denying before reservation/dispatch. Combined with the prior
  review's confirmation of the original three corrections, this covers the final
  implementation. The full final test run was still pending at review time.
  It subsequently passed all 379 cases without code changes after review.
- Final guard/alias/subscription/mixed ownership regression selection:
  **54 passed, 95 deselected** in 55.70s.
- Reviewer source-membership baseline/current comparison:
  **8 passed** in 8.40s (four pre-fix baseline checks and four current checks).
  The initial re-review had four current failures on the identical probe.

The authorized review loop completed three review iterations: initial review
found three P2 defects; first re-review confirmed those fixes and identified the
selection-miss regression; final review cleared the guard. Raw final review:
`/tmp/compaction-stream-membership-review.log`. No commit was authorized or made.

The first focused run exposed incorrect test expectations for existing generic
error translation and malformed-usage normalization. Expectations were corrected
to the existing 502 contracts; neither case silently reuses earlier usage or
becomes cancellation. The application changes remain limited to the three
reviewed corrections.

The final full suites cover **896 distinct passing tests**. Focused selections
are included in those counts; temporary reproductions provide additional
before/after evidence. The final file hashes match the reviewed revision.

Task-only baseline: `/tmp/compaction-review-fixes-baseline/`; final diff:
`/tmp/compaction-stream-contracts-final.patch`. These isolate this correction from
earlier compaction work and unrelated working-tree edits. Test databases are
isolated per process and upstream traffic uses local synthetic HTTP fixtures.
