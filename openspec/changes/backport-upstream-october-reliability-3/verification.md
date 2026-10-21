# Verification: backport-upstream-october-reliability-3

Selective round-3 backport on branch `fix/upstream-backport-round3`, cut from `feature/multi-file-account-import` @ `4940aad2`. Upstream sources are from `Soju06/codex-lb` `origin/main` (`72630bbf`). This is not a release merge.

## Summary

| Dimension | Result |
| --- | --- |
| Completeness | Tasks 1.1–5.3 done. 6.1 is recorded here and 6.2 is synced. 6.3 (archive) waits for operator acceptance. |
| Correctness | Red then green for every fix. Route-level regressions on the direct WebSocket route for #2248 and #2357. Adapter regression on SQLite for #2205. Browser smoke and before/after screenshots for both UI fixes. |
| Coherence | Fork invariants kept: native Codex HTTP stays out of the bridge, round-2 `reset_evidence`, settings-based WS payload budget, warm-up features, capacity replay and owner publication, source routing. No migration, setting or dependency change. `load_balancer_lines` stays at 3021. |

## Commits

| Commit | Content | Upstream |
| --- | --- | --- |
| `15dcd8f5` | OpenSpec change (proposal, design, context, tasks, 8 delta specs) | — |
| `e1b183c7` | retire a denied proxy-injected WebSocket anchor, plus a WS route test | `6b3d031e` (#2248) |
| `a8288693` | shared deadline for the detached-bridge retire sweep | `09b8e891` (#2315) |
| `3b3c1cf8` | anonymous output frames go to the created response, plus a WS route test | `976d20b7` (#2357) |
| `34097fc9` | cached system-trust TLS context for Python WSS | `bb98cdf4` (#2110) |
| `57822dee` | test-only: type the #2248 route-test helper | — |
| `89a17721` | skip unused preparation serialization | `ff6f6a17` (#2113) |
| `55f64f62` | one initial warm-up for fully unused Free quota, plus an adapter test and a routing doc sentence | `a7785a80` (#2205) |
| `ade18e19` | index-bounded conversation presence raw tail | `a408b57a` (#2235) |
| `6240882d` | 60 s trailing-demand memo | `913c6eb5` (#2236) |
| `9c965cd0` | Resume for deactivated accounts, plus screenshots | `0f6a31c5` (#2060) |
| `4e5706a1` | faithful quota chart and per-account panel state, plus screenshots | `ec994599` (#2489) |
| `6a61f7bc` | planner timezone validation | `a3aa8caa` (#2468) |
| `2e9c7265` | planner clock-time validation | `6ed4c44f` (#2540) |
| `3c25bc87` | background state builds follow the dashboard snapshot | `6cdf29ef` (#2233) |

The checkpoint review confirmed that each production backport's patch-id matches its upstream commit.

## Fork adaptations

- **#2248 and #2357:** WebSocket route regressions were added on `/backend-api/codex/responses`.
  - The #2248 test makes its second turn not self-contained, so the denial fails closed.
  - The #2357 test checks request-log attribution, because on a direct WebSocket the client stream is shared.
- **#2113:** the upstream test sizes the WebSocket budget through `settings.max_sse_event_bytes` and calls `_ws_transport_payload_budget_bytes(settings)`, because the fork has no `MAX_SSE_EVENT_BYTES` module constant. The `test_proxy_utils.py` settings stub keeps the fork's fields.
- **#2205:** an integration test proves that the usage-refresh background repository adapter forwards `require_no_prior_attempt`. It lives in `tests/integration/test_atomic_quota_warmup_claims.py` because it needs the DB.
- **#2236 and #2060:** test-only conflicts keep only this commit's additions. The upstream `_disable_background_loop_schedulers` fixture and the #2059 model-source dialog smoke test belong to unported commits.
- **#2233:**
  - `reconcile_recoverable_account_statuses` keeps the fork's `reset_evidence` and gains `dashboard_settings`.
  - The docstring addition is one line, so `load_balancer.py` stays at 3021 lines.
  - Upstream's two MODIFIED `account-routing` requirements are absent in the fork, so a narrower ADDED requirement records the behavior.

## Results (serial, synthetic temp SQLite, DB env overrides unset, empty env file, `TMPDIR=/dev/shm`)

**Phase evidence (base app code → with the pick):**

| Fix | Tests | Before | After | Wider suite |
| --- | --- | --- | --- | --- |
| #2248 | route test | turn 3 re-anchored to the denied id | green | WS `-k 'retires_denied_injected_anchor or previous_response_not_found'` 12 passed; `test_proxy_utils -k anchor` 46 passed |
| #2315 | 3 tests | failed | passed | `-k 'detached or handoff'` 27 passed |
| #2357 | route test | the created response's TTFT was attributed to the sibling | green | WS `-k anonymous` 5 passed; `test_http_bridge_cancel_drain.py` 39 passed; `test_proxy_utils -k anonymous` 16 passed |
| #2110 | 2 tests | 1 failed, 1 error | 2 passed | client files 100 passed |
| #2113 | adapted test | 4 failed | `test_codex_upstream_paths.py` 157 passed | `test_proxy_utils` transport selection 85 passed |
| #2205 | adapter test | `TypeError` | green | warm-up units 112 passed; warm-up integration 35 passed, 8 PostgreSQL-only skips |
| #2235 | statement-shape test | failed | passed | rollup, parity, overview and request-log API 78 passed |
| #2236 | cache tests | errored (missing memo symbols) | 13 passed | weekly pace and overview 46 passed |
| #2060 | screenshot spec | asserted no Resume | asserted Resume | component tests 34 passed; browser smoke 10 passed |
| #2489 | screenshot spec | weekly drawn at 0%; 5h legend on a monthly-only account | merged series; no 5h legend | `src/features/accounts/components` 179 passed |
| #2468 | timezone tests | 6 failed | 8 passed | planner 54 passed |
| #2540 | clock-time tests | 10 failed | 16 passed | planner 70 passed |
| #2233 | 4 tests | failed | passed | recovery 43 passed; load-balancer recover/dashboard 86 passed |

**Global gates on the final tree (`3c25bc87` plus the Phase 15 sync):**
- `ruff check .` and `ruff format --check .`: pass.
- Architecture, cancellation-safety, timing-seam and settings-tier checks: pass. `load_balancer.py` is 3021 lines.
- Baseline-aware `ty` gate: only the 2 baseline diagnostics (`tests/integration/test_model_source_fast_mode.py:67-68`).
- `openspec validate backport-upstream-october-reliability-3 --strict`: valid.
- `openspec validate --specs`: 67 passed, 0 failed.
- Spec-sync block equality (`check_spec_sync.py`): `checked=14 missing=0 duplicate=0 unequal=0`.
- `uv lock --check`: pass.
- Pytest:

| Suite | Result |
| --- | --- |
| `test_proxy_utils.py` | 1425 passed |
| Bridge, cancel-drain and load-balancer units | 1428 passed |
| Client, upstream-path, warm-up, demand-cache, weekly-pace, planner and recovery units | 429 passed |
| Warm-up integration | 45 passed, 8 skipped (PostgreSQL) |
| Presence union, rollups, overview, demand cache, request-log API and planner API | 124 passed, 1 skipped (PostgreSQL) |
| `test_http_responses_bridge.py` | 175 passed |
| `test_proxy_websocket_responses.py` | 164 passed |
| Source dispatch, source WS, WS→HTTP bridge and pool review | 163 passed |

- Frontend:
  - vitest on `src/features/accounts` and `src/features/dashboard`: 46 files, 588 passed;
  - `tsc -b`: exit 0;
  - eslint on the touched files: exit 0.

**End-to-end scenarios on the final tree:**
1. WebSocket route: denied injected anchor not re-sent, 1 passed.
2. Dashboard browser smoke against the real backend: 10 passed (details below).
3. Warm-up adapter plus the SQLite initial-claim race: 2 passed.
4. Planner API (invalid timezone, invalid clock time, dashboard snapshot): 15 passed.
5. Dashboard reads (presence union, demand cache): 4 passed, 1 skipped (PostgreSQL).

**Browser smoke:** `scripts/run_dashboard_browser_smoke.py --frontend-built`, run after `vite build` with a `bun` shim.
- Phase 10: 10 passed, including `deactivated account actions stay inside list cells and responsive cards`.
- Final tree, rebuilt after #2489: 10 passed, including the same test.
- A first attempt at the final run was killed with exit 137 when the session ended, before any test ran. It was rerun alone.

## Screenshots

See `context.md` → "Screenshots". The spec is `frontend/screenshots/upstream-backport-round3.spec.ts`; it uses synthetic fixtures only.

## Baseline failures

None observed in the suites above. The round-2 baseline failure in `test_proxy_overload_soft_affinity.py` lies outside this round's gate set.

## Not run on this host

- **PostgreSQL-only tests:**
  - `test_postgres_warmup_claim_waits_for_older_replica[*]` (8 parameters): the #2205 rolling-upgrade advisory-lock ordering;
  - `test_conversation_union_raw_branch_is_index_bounded_postgresql`: the #2235 `EXPLAIN` probe.
- The full pytest suite and the CI matrix.
- The Docker image build and Python 3.14 product-path tests.
- A successful HA surge deploy would show startup and readiness only. It does not exercise the advisory-lock race.

## Deferred with production evidence (2026-10-20)

- **`b04b2781` (#2387):**
  - The fork keeps native Codex HTTP out of the HTTP bridge unless the transport is explicitly `websocket` (`streaming/retry.py:225-228`), and production runs `auto`. Over 7 days, codex user agents made 25,744 `http→http` requests and none `http→websocket`.
  - The upstream native tests hang on the fork because they assume #2247's promotion.
- **`63314a1b` (#2384):** HTTP-bridge-only instrumentation. Over 7 days `http→websocket` traffic was 114 requests, while the 800 `previous_response_owner_unavailable` errors were all direct WebSocket.

## Post-deploy watch (when deployed)

For 24 h after deploying #2205 (read-only):
- warm-up attempts by status, with about 1,800 expected during the first refresh cycle (an estimated 3–4 h) and a sustained failure rate above the ~2% baseline as the signal;
- upstream 429s and request latency;
- monthly-window freshness and refresh-cycle progress.

Fallback: revert `55f64f62`. This does not undo warm-ups already sent.

## Reviews

- `review-think-20261019-003`: consensus on buckets and adaptations.
- `review-plan-20261020-001`: APPROVE after 3 rounds (9 issues fixed).
- `review-impl-20261020-001` (Phases 1–7, `4940aad2..55f64f62`): APPROVE in round 1, no findings.
- `review-impl-20261021-001` (cumulative `4940aad2..3d7aefb9`): APPROVE in round 1, no findings.
  - Product patches for Phases 8–13 match their upstream patch-ids.
  - Phase 14 keeps `reset_evidence` and stays at 3021 lines.
  - The test-conflict resolutions, the extra typing commit, the integration-test placement and the screenshot fixtures were accepted.
  - The canonical spec changes stay within the approved scope.
