# Verification: fix-model-source-compaction

Verified locally on 2026-10-07. No commit, deployment, production credential or
runtime configuration change is included.

Subsequent review reproduced a transport-error classification defect and a
subscription compact validation regression. The follow-up
[`fix-compaction-review-regressions`](../2026-10-07-fix-compaction-review-regressions/verification.md)
records their corrections and expanded checks; it supersedes this report's
original no-findings conclusion.

| Dimension | Result |
| --- | --- |
| Completeness | All 8 tasks implemented; both added and all 3 modified requirements reviewed |
| Correctness | Public route tests cover source selection, encrypted output, continuity, usage and failures |
| Coherence | Reuses source selection/dispatch/ownership and the existing compact response schema; no provider-specific routing or new setting |

## Requirement evidence

| Requirement | Implementation and coverage |
| --- | --- |
| Responses compaction follows the selected model-source owner | `api.py` selects compact sources before subscription preparation; API tests cover all four HTTP paths, aliases, enforced models, source assignment, disabled/rotated/mixed/unknown owners, file and subscription precedence |
| Compact source forwarding uses the Responses trigger contract | `source_compaction.py` preserves history and creates one trigger, collects actual encrypted output and validates the compact envelope; tests cover compaction summaries, item identity, large output, malformed/absent/truncated output, timeout and disconnect |
| OpenAI-compatible sources route only compatible public routes | Both HTTP Responses handlers retain source eligibility for valid triggers; existing file exclusions and subscription continuity retain precedence; standalone compact trailing slash stays 405 |
| Codex compaction triggers are bridged into compact output | Source SSE uses its existing lifecycle; subscription synthetic lifecycle and v1 duplicate-trigger compatibility pass existing regression tests |
| A disabled model source refuses its models instead of falling through | Compact lookup uses the existing disabled-source denial; both compact and trigger routes refuse disabled sources before reserving usage |

Ownership is published before returning compact JSON using the existing
non-stream finalizer. Tests reset the local source pool and reverse selection
order while keeping the shared database, then replay compact output on its
original source. They also verify failure after disabling or rotating that
source. Persistence failure tests withhold state and release reservations;
success/error/disconnect/timeout assertions verify final reservation state and
zero active source admissions.

## Checks

- `TMPDIR=/dev/shm uv run pytest -q tests/integration/test_model_source_compaction.py
  --timeout=45 --maxfail=3`: **65 passed** on the final implementation.
- Compact regression run across `test_proxy_compact.py`,
  `test_proxy_compact_triggers.py`, `test_api_keys_api.py` and the initial 51-case
  source compact suite, filtered with `-k 'compact or compaction'`: **128 passed**,
  including **77 existing compact/subscription cases**. Together with the final
  expanded source suite, this is 142 distinct compact cases.
- `TMPDIR=/dev/shm uv run pytest -q tests/integration/test_model_source_pool.py
  tests/integration/test_model_source_dispatch.py tests/unit/test_request_policy.py
  tests/unit/test_replay_safety_portability.py tests/unit/test_model_sources_forwarding.py
  --timeout=45 --maxfail=3`: **393 passed**.
- Ruff check and format check: all 8 touched Python files passed.
- `uv run ty check`: changed API, collector, dispatch, forwarding and new
  integration tests passed.
- `python3 scripts/check_proxy_timing_seams.py` and
  `python3 scripts/check_cancellation_safety.py`: passed.
- `git diff --check`: passed.
- Strict change validation: passed. Main specs were synchronized during archive;
  `openspec validate --specs --strict --no-interactive` passed after synchronization.

No critical issues or warnings remain in this scope. Test evidence uses a real
local HTTP provider fixture; replica continuity is simulated by clearing local
selection state, not by deploying a second production backend. The historical
production diagnosis in `context.md` has not been re-run after this local fix.
