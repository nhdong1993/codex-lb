# Verification: fix-compaction-final-review

Local checks on 2026-10-07 for the latest two P2 findings and the related
negative-counter variant found during re-review. All upstream traffic uses
synthetic local HTTP fixtures. No production rollout or commit is included.

## Corrections

- Terminal-root usage is selected only when nested terminal usage is absent or
  null. A selected non-null terminal payload is validated with the strict typed
  usage schema, requires input/output counters and rejects negative known
  counters, including total and usage details. Invalid terminal usage leaves
  the result without usable usage, so the existing limited-key finalizer returns
  `usage_unavailable` without stale fallback, compact output or quota charge.
- Compact requests retain the private provider-reasoning materialization marker
  through policy handling and conversion to Responses. Existing source shaping
  preserves provider aliases, client reasoning summary/effort and API-key
  enforced or allowlisted effort.

## Regression evidence

- Before the first correction, permanent HTTP regressions reproduced **12
  failures**, with 8 passing controls, in 20.85s: six invalid terminal-root cases
  and six provider-alias cases. Log: `/tmp/compaction-final-fixes-before.log`.
- After the first correction, the focused usage/provenance selection passed
  **44 tests** in 46.45s. Full source compaction passed **171 tests** in 173.85s.
- Eight added enforced/allowlisted API-key reasoning controls passed in 9.05s.
- The first re-review cleared reasoning provenance but identified negative
  total/cached/reasoning counters. Twelve permanent cases across both routes and
  nested/root terminal usage all failed before validation was added, in 15.61s.
  Log: `/tmp/compaction-negative-usage-before.log`.
- After strict terminal validation, **48 usage regression tests passed** in
  77.00s, including valid/null precedence and large events.
  Log: `/tmp/compaction-final-usage-focused.log`.
- Final full source compaction suite: **197 passed** in 205.67s.
  Log: `/tmp/compaction-final-fixes-full.log`. Together with the three other
  suites below, this correction has **852 distinct passing permanent tests**.

The 14 original independent review probes also passed in 14.88s, including the
strict provider that previously returned HTTP 400 for duplicate reasoning
controls. Command: `TMPDIR=/dev/shm uv run pytest -q -c pyproject.toml
-p tests.conftest /tmp/compaction-fresh-readonly-review/test_probes.py --timeout=45`.
Log: `/tmp/compaction-original-final-repros.log`. An initial invocation omitted
the repository pytest config and failed to run async tests; the corrected
invocation above explicitly loads it.

## Other checks

- `tests/unit/test_request_policy.py`, `test_model_sources_forwarding.py` and
  `test_source_dispatch.py`: **353 passed** in 4.46s.
- `tests/integration/test_model_source_dispatch.py` and `test_model_source_pool.py`:
  **72 passed** in 79.69s.
- `tests/integration/test_proxy_compact.py`, `test_proxy_compact_triggers.py` and
  `test_api_keys_api.py`: **230 passed** in 200.17s.
- All pytest runs used `TMPDIR=/dev/shm uv run pytest -q` with `--timeout=45`.
- `uvx ruff check .` and `uvx ruff format --check .`: passed (1204 files).
- `uv run ty check` for all four changed Python files: passed.
- Full-repository `uv run ty check` remains non-green with two diagnostics
  outside this correction: a dict passed to `ProxyResponseError` at
  `tests/integration/test_proxy_chat_completions.py:109`, and an assignment to
  `catalog_server.payload` at `tests/unit/test_key_dashboard_install.py:204`.
  These files were not changed by this correction.
- Proxy timing seam, cancellation safety and `git diff --check`: passed.
- Strict active-change validation: passed. Main specs after sync/archive: **67 passed, 0 failed**.

An additional local audit reproduced a Pydantic error escaping as HTTP 500
when earlier observed usage had a boolean input counter and terminal usage was
absent. Restoring the original validation catch around usage reconstruction
keeps this an upstream 502 error. The 52-case usage and boolean
regression selection then passed in 54.22s; two cached-boolean cases were added
for the final full run. Six HTTP regression cases cover input/output/cached
booleans on both routes, including quota release and error logging. Pre-fix
reproduction: `/tmp/compaction-observed-bool-before.log`.

## Review

The user authorized fixes following the fresh review's two P2 findings. The
first Codex CLI re-review confirmed provenance and found the negative-counter
variant; the validator and 12 HTTP regressions address that finding. The final
re-review confirmed terminal strictness (49 invalid cases), precedence/no-
fallback (9 cases) and private provenance (3 cases), then reproduced the same
boolean-observation regression found by the local audit. The validation guard
was restored and the API regressions above verify the correction.

The loop completed its three review iterations (initial review and two
re-reviews). The final guard restoration is test-verified but was not subjected
to a fourth independent review. There are no known unresolved findings; this
is not a claim that the final reviewer returned a clean verdict. The loop is
scoped to this compaction correction; unrelated working-tree changes and
production behavior are not reviewed.

The pre-fix baseline is `/tmp/compaction-final-fixes-baseline/`, task-only patch
is `/tmp/compaction-final-fixes.patch`, and reviewed file hashes are in
`/tmp/compaction-final-fixes.sha256`. Raw review logs are
`/tmp/compaction-final-fix-rereview.log` and
`/tmp/compaction-final-validation-review.log`. Focused subsets are included in
the full suite counts, not counted again as distinct tests.
