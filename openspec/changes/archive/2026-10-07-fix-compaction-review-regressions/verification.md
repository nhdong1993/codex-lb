# Verification: fix-compaction-review-regressions

Verified locally on 2026-10-07. Both review findings are resolved; no commit,
deployment, restart or production configuration change was performed.

| Dimension | Result |
| --- | --- |
| Completeness | Both corrections and public-route regressions implemented |
| Correctness | Broken TCP streams return 502/error; subscription compact extras retain their accepted shape |
| Coherence | Shared selection and ownership helpers now accept compact requests; existing dispatch finalizers still own cleanup |

## Evidence

The broken-stream fixture waits until the source open has returned, then aborts
the actual HTTP connection after `response.created`. Both standalone compact
routes return `502 model_source_unreachable` with an upstream-error envelope.
Tests assert a single source call, an error log with source/revision and upstream
status 200, a released reservation and zero source admissions. This prevents a
mid-stream failure being confused with either client cancellation or a retryable
connection-establishment failure.

Both compact routes accept the existing subscription extras
`conversation: {"id": "conv_existing"}` and provider-specific `text.format`.
Subscription previous-response ownership, turn-state ownership and file pins
also preserve those extras when a source exposes the same model. Source-owned
validation failures remain 400 before dispatch; they do not fall back to an
account. Separate cases disable every source and prove retained encrypted or
previous-response references still yield 409 before another reservation,
including surrounding whitespace in the previous-response ID.

## Checks

- Initial regression selection across `test_model_source_compaction.py` and
  `test_proxy_compact.py`: **14 passed**.
- `TMPDIR=/dev/shm uv run pytest -q tests/integration/test_model_source_compaction.py
  tests/integration/test_proxy_compact.py tests/integration/test_proxy_compact_triggers.py
  tests/integration/test_api_keys_api.py -k 'compact or compaction' --timeout=45 --maxfail=3`:
  **150 passed, 149 deselected**.
- After normalizing compact previous-response references for ownership lookup,
  `TMPDIR=/dev/shm uv run pytest -q tests/integration/test_model_source_compaction.py
  -k source_lookup_miss --timeout=45 --maxfail=1`: **4 passed, 69 deselected**.
  These four cases were added after the broader suite began, yielding 154
  distinct passing compact/subscription cases.
- `TMPDIR=/dev/shm uv run pytest -q tests/integration/test_model_source_pool.py
  tests/integration/test_model_source_dispatch.py tests/unit/test_request_policy.py
  tests/unit/test_replay_safety_portability.py tests/unit/test_model_sources_forwarding.py
  --timeout=45 --maxfail=3`: **393 passed**.
- Ruff check, Ruff format check and `uv run ty check` passed for the three changed
  Python files: proxy API and the two compact integration suites.
- `python3 scripts/check_proxy_timing_seams.py`,
  `python3 scripts/check_cancellation_safety.py` and `git diff --check`: passed.
- Strict OpenSpec change validation: passed. After synchronization and archive,
  `openspec validate --specs --strict --no-interactive`: **67 passed, 0 failed**.

All 547 distinct regression cases above passed. The initial 14 are included in
the broader count. Final code was reviewed against the pre-fix working-tree
baseline, preserving unrelated edits. These checks use a local synthetic HTTP
upstream; production rollout has not been tested.
