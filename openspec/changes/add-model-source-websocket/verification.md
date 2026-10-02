# Verification: model source WebSocket

Initial local verification was on 2026-09-29. The native sequential runtime, default-off capability, dashboard control and catalog/installer policy are implemented. Stable specifications and user documentation are synced. The subsequent F23/F24 corrections are implemented, their focused regression suite passes **102 cases**, and the independent fix review returned no actionable findings. Earlier implementation and review evidence remains below. The change is **not ready for archive or production enablement** while the outstanding client/provider, PostgreSQL and release gates remain.

The F25 HTTP ownership-envelope regression is corrected and locally verified
on 2026-10-02. The correction preserves `server_error` across HTTP and WebSocket
ownership denials; see [the latest review disposition](notes.md).

## F25 correction checks — 2026-10-02

| Check | Result |
| --- | --- |
| New response/item ownership regressions before the fix | **16 failed** at the HTTP error-envelope assertion, 17.82s |
| Complete error-contract file after the fix | **60 passed**, 61.58s |
| Source pool, prompt/metadata/standalone-output and native WebSocket/policy compatibility | **257 passed**, 333.64s; one existing AnyIO deprecation warning |
| Independent correction review | **No actionable findings**; 209 targeted integration passes, overlapping mapped coverage |
| Whole-repository Ruff and formatting | Passed; **1188 files** already formatted in isolated correction tree |
| Affected-file type checks; timing/cancellation checks | Passed |
| Strict change/main-spec validation | Passed; **67 specs**, zero failures |
| Full local CI | `make ci` stopped because Bun is unavailable on the host |
| Whole-repository type checks | One pre-existing error at `tests/unit/test_key_dashboard_install.py:204` |

```bash
env -u CODEX_LB_TEST_DATABASE_URL TMPDIR=/dev/shm .venv/bin/python -m pytest -q \
  tests/integration/test_model_source_websocket_error_contract.py \
  --timeout=90 --tb=short --show-capture=no

env -u CODEX_LB_TEST_DATABASE_URL TMPDIR=/dev/shm .venv/bin/python -m pytest -q \
  tests/integration/test_model_source_pool.py \
  tests/integration/test_source_prompt_compatibility.py \
  tests/integration/test_source_pool_standalone_outputs.py \
  tests/integration/test_source_client_metadata.py \
  tests/integration/test_model_source_websocket.py \
  tests/integration/test_model_source_websocket_policy_review.py \
  --timeout=90 --tb=short --show-capture=no
```

The 16 new cases check exact envelopes on both transports, disabled-source
response/item ownership, capability off/on and all four URLs. A rejected turn
leaves only the preceding successful request's finalized reservation and never
reaches the provider. The compatibility suite and independent review ran in
an isolated checkout containing only this correction over `976b42d5`.

HA preflight observed three healthy eligible base backends, no rollout in
progress, public readiness, 52 PostgreSQL connections out of 100, the existing
WebSocket migration at head and zero sources with the native flag enabled.
The candidate is planned as the current production image plus the F25 helper
correction so already deployed unrelated changes are preserved. These are
preflight observations, not a deployment-success claim.

## Completeness and coherence

| Area | Assessment |
| --- | --- |
| Tasks | 42/47 complete; F25 locally verified; five original client/provider/database/release gates remain |
| Requirements | Runtime implementation found for all 11 new requirements and three modified requirements; the unconditional source WS prohibition is removed |
| Design | Dedicated native adapter and session owner; shared HTTP candidate shaping, ownership observation and dispatch accounting; no subscription account emulation |
| Activation | Capability defaults false; no existing source or production configuration was enabled |
| Publication | Feature commit `976b42d5`; this document records F25 verification before the requested correction publication and HA rollout |

The implementation shares preparation with HTTP instead of duplicating candidate ownership rules. Subscription routing remains inside its existing session service. Its reader hands source traffic to the native owner before subscription normalization/reservation, and both paths share the downstream send lock. Quota acquisition defers cancellation until its result has an owner; settlement failures stop reuse and handshake retries. Generation cleanup cancels and awaits its reader, worker, lifecycle and heartbeat tasks.

## Requirement and scenario evidence

| Contract/scenarios | Implementation | Evidence |
| --- | --- | --- |
| Default false, PATCH omission, resulting-state validation | `app/db/models.py`, `20260929_000000_add_source_websocket.py`, model-source schemas/service | Migration backfill, repeated upgrade, downgrade/upgrade, schema drift; management validation and existing management/frontend regressions |
| Both route families and slash variants; public/upstream aliases; policy before reservation | `proxy/api.py` source callback and `_resolve_source_response_candidates` | Four actual ASGI route variants, two turns per socket, alias continuity, disabled/unauthorized/revoked source, lookup outage, override-introduced file rejection; existing source HTTP and subscription routing regressions |
| Endpoint/credential isolation, no redirect | `model_sources/websocket.py` | Real local 401/403/429/500/302 handshakes, source-only Authorization; HTTP/HTTPS custom path conversion, absent credentials, trust-env on/off and bounded connect parameters |
| Sequential/tool/warmup profile; one waiting turn; unsupported controls | `proxy/source_websocket.py` | Tool call/result IDs on one connection, queue saturation and receipt-based expiry, warmup with zero/missing usage, withheld unexpected output, binary/malformed events and oversized parser input |
| Immutable identity and fresh per-turn policy | Source callback, `SourceSocketIdentity` | Source disablement, capability removal, credential rotation, reassignment, revocation and model changes between turns; subscription-to-source switch requires reconnect without a source reservation, and the subscription connection remains usable |
| Publication before delivery; cross-transport ownership | `source_ownership.py`, `SourceStreamUsageParser.observe_event` | HTTP → WS → HTTP response ID continuity; publication failure withholds output; existing durable ownership/history tests cover conflicts and historical references |
| Exactly one finalizer; retry only before send | `SourceDispatch`, native worker | Limited-key success/missing usage/incomplete/error/truncated/cancel paths; handshake retry policy and no redirects; no retry after send, release failure stops retry/cooldown, settlement failure stops the next turn, cancellation during quota acquisition releases the committed reservation |
| Transport-family isolation and global HTTP | Handshake gate and source pool | Source works during a subscription WS failure marker; global HTTP yields 426 and disables source preference; account/subscription fallback regressions pass |
| Bounded sockets/tasks and drain | Existing WebSocket bulkhead, source lifecycle, inflight middleware | Idle close, slow downstream send cancellation, first-frame timeout on reused socket, concurrent session admission before quota, idle/active drain and released claims |
| Conservative catalog and installer | `catalog.py`, `websocket_capability.py`, key-dashboard API | Source-only capable/incapable keys on macOS/Linux/Windows, mixed-capability pools including nonstreaming equivalents, global HTTP; existing frozen export and other assignment-class regressions |

Cross-replica continuity is implemented through the existing durable store and credential revision hash. The local acceptance suite proves cross-request/transport continuity, not a live multi-replica provider session. No claim is made that a provider can restore connection-local state after reconnect.

## Additional review after F23–F24 — 2026-10-01

| Check | Result |
| --- | --- |
| Seven native/transport files in one sequential process | **284 passed**, 302.01s; one AnyIO deprecation warning; `/tmp/source-ws-review-after-f24/native.log` |
| New HTTP ownership-error reproduction, both route families/slashes | **4 failed, 4 passed** in 9.19s; all failures use current code and all passing controls restore only the HEAD HTTP helper |
| Independent supplementary cases | **10 passed** across control/warmup/identity/ownership checks |
| Independent mapped transport/lifecycle/policy checks | **45 passed** across two runs; overlaps the parent native suite |
| Independent review | Completed with **one P2 finding (F25)**; `/tmp/source-ws-review-after-f24/independent.log` |

```bash
env -u CODEX_LB_TEST_DATABASE_URL TMPDIR=/dev/shm .venv/bin/pytest -q -x \
  tests/integration/test_model_source_websocket.py \
  tests/integration/test_model_source_websocket_review.py \
  tests/integration/test_model_source_websocket_policy_review.py \
  tests/integration/test_model_source_websocket_lifecycle_review.py \
  tests/integration/test_model_source_websocket_input_discovery.py \
  tests/integration/test_model_source_websocket_error_contract.py \
  tests/unit/test_model_source_websocket_transport.py \
  --timeout=90 --tb=short
```

This review did not alter application code or tests. The fresh combined run
did not reproduce the previous timeout and does not establish its cause or
disk-backed stability. F25 is an uncovered HTTP-envelope assertion, not a
failure in the existing native suite. Real client/provider, PostgreSQL and
native Windows execution checks remain unverified.

## F23–F24 correction checks — 2026-10-01

Application changes in this pass are limited to
`model_sources/websocket_capability.py` and `proxy/api.py`. There are **55 new
regression cases**: 11 eligibility/export/catalog cases and 44 domain-error cases
with unchanged HTTP controls. The 102-case run also includes the 47 prior
input-limit/effective-model cases.

| Check | Result |
| --- | --- |
| Error-contract and input/discovery suites, sequential isolated SQLite on tmpfs | **102 passed**, 120.34s; `/tmp/source-ws-f23-f24-regressions-sequential.log` |
| Mapped subscription, installer/catalog and source policy/review compatibility | **317 passed, 19 skipped**, 334.78s; one AnyIO deprecation warning; `/tmp/source-ws-f23-f24-compat-sequential.log` |
| Original review reproductions | **16 passed, 1 receive timeout** in 145.32s; the unchanged timeout case then **passed** in isolation in 10.10s |
| Independent snapshot-scoped review | **No actionable findings**; 18 supplementary cases passed across two runs, including queued errors and provider redaction |
| Whole-repository Ruff and format check | Passed; **1190 files** already formatted |
| Type checks for the two application files and two regression files | Passed |
| Whole-repository type check | Two existing out-of-scope test errors, listed below |
| Timing seams and cancellation safety scripts | Passed |
| Strict change/main-spec validation | Passed; **67 specs passed, 0 failed** |

```bash
env -u CODEX_LB_TEST_DATABASE_URL TMPDIR=/dev/shm .venv/bin/pytest -q -x \
  tests/integration/test_model_source_websocket_error_contract.py \
  tests/integration/test_model_source_websocket_input_discovery.py \
  --timeout=90 --tb=short

env -u CODEX_LB_TEST_DATABASE_URL TMPDIR=/dev/shm .venv/bin/pytest -q -x \
  tests/integration/test_proxy_websocket_responses.py \
  tests/integration/test_key_dashboard_install_catalog.py \
  tests/unit/test_key_dashboard_install.py \
  tests/unit/test_model_sources_catalog.py \
  tests/integration/test_model_source_websocket_policy_review.py \
  tests/integration/test_model_source_websocket_review.py \
  --timeout=90 --tb=short

.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

The 19 skips all require unavailable PowerShell (`pwsh`). The new three-platform
export assertions did run, including generated Windows configuration; native
Windows execution/ACL behavior is not certified by this pass.

The initial parallel disk-backed runs did not complete cleanly. The regression
run reached **62 passed, 1 timeout failure and 1 setup error** before interruption;
the compatibility run also timed out and was terminated during interrupted
cleanup. Captured stacks show SQLite WAL connection/transaction cleanup, and a
fixture reset raised `PendingRollbackError` after interruption. Their logs are
`/tmp/source-ws-f23-f24-{regressions-final,compat}.log`. The sequential rerun uses
independent SQLite files on `/dev/shm`, with the same application, assertions
and 90-second test timeout. This provides functional evidence, not a diagnosis
or fix of the earlier disk-backed timeout. The original receive timeout log and
isolated pass are `/tmp/source-ws-f23-f24-{original-repros,timeout-isolated}.log`.

An earlier superseded run used an incorrect new quota fixture: reducing the
maximum while consumption was zero did not exhaust quota. The final fixture
waits for prior settlement when reusing the socket, then exhausts the limit's
current value. The superseded run is not counted as application-failure or
passing evidence.

Whole-repository type checking retains the previously observed diagnostics at
`tests/integration/test_proxy_chat_completions.py:109` (dictionary error envelope)
and `tests/unit/test_key_dashboard_install.py:204` (JSON payload assignment).
Neither file was changed in this correction pass. Review evidence is
`/tmp/source-ws-f23-f24-independent-review.log`; the independent checks did not
certify external clients/providers or PostgreSQL.

## Executed checks

Commands use the repository `.venv` (Python 3.14.7). Bun is absent in this environment, so frontend checks use Node to invoke the installed tools. Results are for focused checks, not the entire repository test suite; overlapping suites must not be summed as unique tests.

| Check | Result |
| --- | --- |
| Native public routes and transport adapter: command A | **67 passed** (55 integration, 12 adapter) |
| Existing source routing, legacy source guards and catalog: command B | **160 passed** |
| Dispatch owner, source pool and catalog unit regressions | **165 passed** |
| Model-source management service unit regressions | **5 passed** |
| Existing dispatch, ownership/history storage and installer: command C | **50 passed, 2 skipped**; skips require PostgreSQL |
| Subscription WS, transport fallback and account availability: command D | **219 passed** |
| SQLite migrations: command E | **6 passed** |
| Frontend model-source tests: command F | **29 passed**, four files |
| Frontend TypeScript and affected ESLint | Passed |
| Affected Python Ruff and application type checks | Passed |
| Proxy timing seams and cancellation safety scripts | Passed |
| Strict change validation and strict main specs validation | Passed; main specs **67 passed, 0 failed** |
| UI before/after captures | Both Playwright runs passed; dependency checkboxes asserted |

```bash
# A
.venv/bin/pytest -q tests/integration/test_model_source_websocket.py tests/unit/test_model_source_websocket_transport.py --timeout=120

# B
.venv/bin/pytest -q tests/unit/test_proxy_websocket_model_source_guard.py tests/unit/test_model_sources_catalog.py tests/integration/test_model_source_routing.py --timeout=120
.venv/bin/pytest -q tests/unit/test_source_dispatch.py tests/unit/test_source_pool.py tests/unit/test_model_sources_catalog.py --timeout=120
.venv/bin/pytest -q tests/unit/test_model_sources_service.py --timeout=120

# C
.venv/bin/pytest -q tests/integration/test_model_source_dispatch.py tests/integration/test_source_ownership_storage.py tests/integration/test_source_ownership_history_storage.py tests/unit/test_key_dashboard_install.py --timeout=120

# D
.venv/bin/pytest -q tests/integration/test_proxy_websocket_responses.py tests/unit/test_websocket_transport_fallback.py tests/integration/test_proxy_websocket_account_availability.py --timeout=120

# E
.venv/bin/pytest -q tests/integration/test_model_source_websocket_migration.py tests/integration/test_source_ownership_migration.py tests/integration/test_source_ownership_history_migration.py tests/integration/test_reset_credit_outcome_migration.py tests/integration/test_subscription_migration.py tests/integration/test_new_account_warmup_migration.py --timeout=120

.venv/bin/python scripts/check_proxy_timing_seams.py
.venv/bin/python scripts/check_cancellation_safety.py
npx --yes @fission-ai/openspec@1.11.0 validate add-model-source-websocket --strict
npx --yes @fission-ai/openspec@1.11.0 validate --specs --strict

# F: run in frontend/
node node_modules/vitest/vitest.mjs run src/features/model-sources
node node_modules/@typescript/native/bin/tsc -b
node node_modules/eslint/bin/eslint.js src/features/model-sources src/test/mocks/factories.ts screenshots/source-websocket.config.ts screenshots/source-websocket.spec.ts
npx playwright test --config screenshots/source-websocket.config.ts
```

Screenshots: [before](evidence/form-before.png), [after](evidence/form-after.png). The before capture used an isolated frontend copy with the feature's form files restored to HEAD; it did not revert working-tree files. The screenshot fixture mocks dashboard APIs and asserts that selecting WebSocket selects Responses and Streaming. Its assertions cover the source form; unrelated background settings requests use placeholder responses and emitted schema warnings.

## Review correction checks — 2026-09-30

After the first review confirmed nine bugs, the user authorized all fixes and a
second review. [notes.md](notes.md) maps each finding to the implementation and
regression coverage. The following checks validate the corrected implementation,
separately from the original acceptance results above.

| Check | Result |
| --- | --- |
| Final public-route regression suite after iteration-2 corrections | **45 passed** in 105.42s; retrieved after the sandbox was restored |
| Fresh public-route regression rerun during the additional review | **45 passed** in 93.64s, one AnyIO deprecation warning; `/tmp/source-ws-fresh-current-regressions.log` |
| Existing native routes, adapter and SQLite capability migration after iteration-2 corrections | **68 passed** in 177.09s |
| Affected Ruff check and format | Passed |
| Affected application/test type checks | Passed |
| Cancellation safety and proxy timing seams | Passed |
| Strict change and main-spec validation | Passed; **67 main specs passed** |
| Shared HTTP source/subscription/dispatch/pool regressions before iteration-2 corrections | **378 passed**, 7 warnings, in 444.84s |
| Independent review iteration 3 | F12 active-deadline and F13 heartbeat defects confirmed despite passing regressions |
| Additional manual review | F12/F13 reproduced: **4 failed, 1 passed**; F14 initial-lookup drain/disconnect: **2 failed**; F15 selection/admission race: **1 failed** |
| Subscription turn-state ownership review | F16 reproduced on both route families: **2 failed, 2 passed**; controls disable only the new source callback |
| Additional independent review requested by the user | Complete: confirms F12–F16 (**1 P1, 4 P2**); fresh deadline/heartbeat reproductions **4 failed, 1 passed**, independent turn-state reproductions **2 failed, 2 passed** |

```bash
.venv/bin/pytest -q tests/integration/test_model_source_websocket_review.py
.venv/bin/pytest -q tests/integration/test_model_source_websocket.py \
  tests/unit/test_model_source_websocket_transport.py \
  tests/integration/test_model_source_websocket_migration.py
.venv/bin/pytest -q tests/integration/test_proxy_websocket_responses.py \
  tests/unit/test_websocket_transport_fallback.py \
  tests/integration/test_proxy_websocket_account_availability.py \
  tests/integration/test_model_source_dispatch.py \
  tests/unit/test_source_dispatch.py tests/unit/test_source_pool.py --timeout=120
```

All new route tests use the isolated test database and local provider fixture.
Earlier iterations corrected fixture expectations for the subscription path's
released reservation and its alternate `response.failed` envelope; neither
permits a source dispatch. Tests also verify that a known failed terminal
releases quota, successful warmup retains settlement, and a terminal withheld
by ownership publication is not billed as successful delivery.

## Latest correction checks — F12–F20

The user authorized F12–F16 corrections and continued the fix/review work.
F17/F18 were found by the independent CLI review during that work and corrected
with eight further actual-route cases. F19/F20 were found while rerunning the
subscription and source deadline paths. [notes.md](notes.md) maps all nine bugs
to code changes and tests. The current focused checks are:

| Check | Result |
| --- | --- |
| Final native source matrix after F20 | **183 passed** in 399.36s: 42 lifecycle, 28 policy/admission, 45 prior review, 55 native route, 12 adapter and 1 SQLite migration cases; `/tmp/source-ws-final-183.log` |
| Shared source dispatch/HTTP integration and dispatch/pool unit regressions | **159 passed** in 83.49s; `/tmp/source-ws-dispatch-final-matrix.log` |
| Final subscription WebSocket/fallback/account availability regressions after F20 | **219 passed** in 259.14s; `/tmp/source-ws-subscription-final-after-f20.log` |
| Exact original F12–F16 reproductions | **7 passed** plus **9 passed** in separate isolated fixtures |
| Exact independent F17/F18 reproductions | **3 passed** in 15.12s; `/tmp/source-ws-independent-edges-parent-final.log` |
| F19 subscription-only validation, corrected source create, and existing backend-switch/handoff controls | **14 passed**, 122 deselected, in 56.48s; four new cases cover both routes; `/tmp/source-ws-binding-final.log` |
| Exact independent F19 reproduction | **1 passed** in 3.75s; `/tmp/source-ws-binding-edge-fixed.log` |
| F20 stream-budget source active-turn regression | **6 passed** within the final 183-case matrix: longer stream budget, shorter stream budget and missing-setting fallback on both public routes |
| F20 control restoring the previous generic-budget behavior | **2 expected failures** in 5.36s, both at the external `response.completed` assertion after receiving an early error; `/tmp/source-ws-f20-old-budget-control.log`. The control changes only the isolated test process through a temporary plugin. |
| Subscription sequential-turn fixture correction | **1 passed** in 2.76s after correction and passed again within the final 219-case subscription matrix |
| Whole-tree Ruff check and format | Passed; **1188 files** formatted |
| Affected application/test type checks, including shared cleanup protocol | Passed |
| Whole-tree type check | The same **two unrelated test errors** listed below; the stale cleanup protocol annotation found in this pass was fixed |
| Proxy timing seams and cancellation safety | Passed |
| Strict change and main-spec validation | Passed; **67 main specs**, zero failures |
| Independent review | CLI reproduced F17–F20 before the same model/account failure; no clean final report was returned |

The earlier 173-case combined invocation returned **172 passed, 1 failed** in
528.67s. Its heartbeat control signalled before the first touch committed,
allowing that same touch to
be mistaken for a later retry. The fixture now signals after commit, and all
32 lifecycle cases pass together. Earlier one-second setup deadlines were
replaced with the supported Clock seam. The existing HTTP stall test now waits
for upstream arrival before advancing the clock; its earlier fixed sleep
included request preparation and did not guarantee time spent stalled.

The recovered reviewer later reproduced F19: subscription-specific validation
could bind an invalid first create and prevent a corrected source create. Binding
now follows successful preparation. Four new cases plus existing handoff and
backend-switch controls pass. F20 added six budget cases, bringing the final
native matrix to **183 passing cases in one run**. The first post-F19 subscription
run returned **218 passed, 1 failed** in 278.97s. The failing sequential-turn
fixture emitted its second response batch before the second request was sent;
each batch now waits for its corresponding send. Its focused rerun and the full
219-case subscription rerun passed. Both final matrices emitted only the AnyIO
deprecated-alias warning. The parent manually rechecked budget precedence,
retry deadlines, terminal accounting and subscription binding without identifying
another defect in these corrections. The independent review service did not
return a completed final report.

```bash
.venv/bin/pytest -q tests/integration/test_model_source_websocket_lifecycle_review.py \
  tests/integration/test_model_source_websocket_policy_review.py \
  tests/integration/test_model_source_websocket_review.py \
  tests/integration/test_model_source_websocket.py \
  tests/unit/test_model_source_websocket_transport.py \
  tests/integration/test_model_source_websocket_migration.py --timeout=120
.venv/bin/pytest -q tests/integration/test_model_source_websocket_lifecycle_review.py --timeout=120
.venv/bin/pytest -q tests/integration/test_model_source_dispatch.py \
  tests/unit/test_source_dispatch.py tests/unit/test_source_pool.py --timeout=120
.venv/bin/pytest -q tests/integration/test_proxy_websocket_responses.py \
  tests/unit/test_websocket_transport_fallback.py \
  tests/integration/test_proxy_websocket_account_availability.py --timeout=120
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/check_proxy_timing_seams.py
.venv/bin/python scripts/check_cancellation_safety.py
npx --yes @fission-ai/openspec@1.11.0 validate add-model-source-websocket --strict
npx --yes @fission-ai/openspec@1.11.0 validate --specs --strict
```

All application tests in this pass use isolated SQLite databases and local
upstreams. No live credentials, production database, external inference or
provider activation was used. Earlier parallel runs also encountered a SQLite
startup/teardown timeout; the relevant subscription-handoff route matrix passed
on rerun and in the final lifecycle matrix. AnyIO deprecation and aiosqlite
thread teardown warnings remain recorded in the logs.

## F21–F22 verification

The first source create now uses its original UTF-8 wire size, retained by the
shared input buffer, before source admission. Catalog and installer capability
now use shared source candidate rules after effective key/alias/fast-mode policy.
The corrections are documented in [notes.md](notes.md).

| Check | Result |
| --- | --- |
| New input/discovery route matrix, all four paths and all installer platforms | 40 passed in 166.93s |
| Additional effective-pool assignment, allowlist, disabled and non-streaming controls | 5 passed in 21.08s |
| Buffered correction after oversized initial create, both routes | 2 passed in 9.86s |
| Existing HTTP source routing aliases, enforcement, disabled-source and permission cases | 22 passed, 87 deselected in 119.10s |
| Ruff check and format | Passed, 1189 files formatted |
| Affected application/test type checks | Passed |
| Full-repository type check | Same two pre-existing unrelated test diagnostics listed below |
| Proxy timing seams and cancellation safety | Passed |
| Strict change and main-spec validation with OpenSpec 1.11.0 | Passed; 67 main specs |
| Existing subscription WebSocket, selection, catalog and installer suites | 339 passed, 19 skipped (PowerShell unavailable), 7 warnings in 723.47s |
| Existing native suite | All 55 base cases passed in the combined rerun; the remaining four files passed 127 cases in 277.48s. The combined rerun hit one intermittent cleanup timeout and was interrupted after 70 passed / 1 failed; see disposition below. |
| Ordered handshake-retry, zero-grace drain, earliest-deadline and admission-race controls after fixture correction | 20 passed in 56.77s |
| Independent fix review | Completed with no actionable findings; 29 additional isolated route/control checks passed in 123.79s |

Test logs: `/tmp/source-ws-f21-f22-{regressions,scopes,buffered,http-selection,native,compat}.log`.
All tests use isolated SQLite and local provider stubs. The HTTP selection
run passed but emitted the existing aiosqlite thread/event-loop teardown warning.
No production database or source was used. The pre-fix snapshot under
`/tmp/source-ws-f21-f22-before/` scopes the independent reviewer to this fix pass.
Its completed report is `/tmp/source-ws-f21-f22-review.log`; additional tests and
results are under `/tmp/codex-ws-f21f22-fix-review/`. The first attempt at those
fixtures had incorrect input-normalization/allowlist/catalog-quota assumptions;
the corrected 29-case matrix passes. None were confirmed implementation defects.

The first combined native run returned 171 passed and 11 failed. A minimal
two-test sequence reproduced the cross-file failure: the handshake fixture
patched the process-wide pool instance's `choose` method, so monkeypatch undo
left a bound instance method that masked later class-level race controls. The
fixture now patches `SourcePool` at the class level. The zero-grace drain test
also observed reservations after a fixed sleep even though settlement had been
transferred to tracked background cleanup; it now awaits socket closure and the
service-owned cleanup before asserting settlement. The unchanged standalone
policy suite passed 28/28; after these fixture corrections the ordered 20-case
control passes. Evidence: `/tmp/source-ws-f21-f22-order-before.log` (1 failed,
1 passed) and `/tmp/source-ws-f21-f22-order-after.log` (20 passed). These fixture
changes do not alter production selection, drain or accounting behavior.

The subsequent combined run passed those corrected fixtures but hit a separate
five-second cleanup wait in the withheld-terminal partial-delivery test on the
backend route. Its socket had already closed within the asserted three-second
bound; the failure occurred while waiting for service-owned persistence, with
another SQLite commit timing out during teardown. That run was interrupted to
retrieve the traceback (70 passed, 1 failed). All six unchanged withheld-usage
variants passed in isolation in 22.60s. This does not establish a fully clean
combined native run or a proven cause for that intermittent cleanup timeout.
Logs: `/tmp/source-ws-f21-f22-native-final.log` and
`/tmp/source-ws-f21-f22-withheld-control.log`. The remaining four native files
subsequently passed 127/127 in 277.48s, with one AnyIO deprecation warning;
`/tmp/source-ws-f21-f22-native-remainder.log`. This run includes the unchanged
failing test and the policy controls that previously suffered from fixture
contamination. No application code changed after the independent fix review.

The mapped suite commands for this fix pass were:

```bash
env -u CODEX_LB_TEST_DATABASE_URL .venv/bin/pytest -q \
  tests/integration/test_proxy_websocket_responses.py \
  tests/unit/test_proxy_websocket_model_source_guard.py \
  tests/unit/test_model_sources_selection_overflow.py \
  tests/unit/test_model_sources_catalog.py \
  tests/unit/test_key_dashboard_install.py \
  tests/integration/test_key_dashboard_install_catalog.py \
  tests/integration/test_v1_models.py --timeout=90

env -u CODEX_LB_TEST_DATABASE_URL .venv/bin/pytest -q \
  tests/integration/test_model_source_routing.py \
  -k 'alias or allowed or enforc or disabled or source_scop' --timeout=90

env -u CODEX_LB_TEST_DATABASE_URL .venv/bin/pytest -q \
  tests/integration/test_model_source_websocket.py \
  tests/integration/test_model_source_websocket_lifecycle_review.py \
  tests/integration/test_model_source_websocket_policy_review.py \
  tests/integration/test_model_source_websocket_review.py \
  tests/unit/test_model_source_websocket_transport.py --timeout=90
```

## Outstanding gates and limitations

**Must complete before archive:**

- **Additional review findings:** Correct and verify F23/F24 from the 2026-10-01 review before readiness. Actual route/export reproductions fail on the current implementation; the existing native suite does not cover those cases.

- **Local native cleanup validation (7.4):** The 2026-10-01 combined run passed all 182 cases in 524.67s with one AnyIO warning, using a temporary read-only task-stack observer (`/tmp/source-ws-review-after-f22/cleanup_probe.py`). The former five-second cleanup timeout did not recur; this provides clean combined-run evidence but does not identify the original cause. Retain the historical failure when assessing test stability. F21/F22 fix verification and independent review (8.10/8.16) remain historical completed checks; they do not override the new F23/F24 findings.

- **1.2 and 5.5:** Exercise the intended client version against both handshake 426 and accepted-socket errors, with source-only/mixed assignments and connection reuse. The local fixture verifies envelopes; it does not establish that a particular client automatically falls back to HTTP. Named lanes, steering and application cancellation remain unsupported.
- **1.3:** Select the intended provider and run endpoint/auth, two-turn tool continuation, warmup, reconnect and failure conformance in staging before enabling its flag. No external inference or real provider credential was used here.
- **2.1:** Run the migration and storage regressions against an isolated PostgreSQL database. SQLite migration and single-head checks passed; PostgreSQL execution was unavailable locally (Docker API access was denied). No production database was used for validation.
- **7.4:** Complete the above, verify any deployment/client conformance evidence and archive the change. For a later PR, follow the recorded review slices and check actual current-head CI, CodeRabbit threads and mergeability. Local results do not satisfy those cloud gates.

**Validation observations:**

- Full-repository `ty check --output-format concise` reports two errors outside this feature's edits: `tests/integration/test_proxy_chat_completions.py:109` constructs `ProxyResponseError` with an untyped dict, and `tests/unit/test_key_dashboard_install.py:204` assigns a value incompatible with its annotated JSON payload. Affected application checks pass. A clean baseline for all unrelated working-tree edits was not established.
- Subscription tests emitted an AnyIO deprecated alias warning and aiosqlite thread/event-loop shutdown warnings. Passing native runs emitted the AnyIO warning through subscription-switch fixtures. The separate combined-run cleanup timeout is recorded above; passing focused checks are not treated as proof of clean whole-repository teardown.
- Earlier runs under shared host load hit fixture timeouts and one existing wall-clock source-stall assertion. The focused rerun in command C passed. The shared-dispatch AST guard was updated to recognize the new source preparation entry point and passed on rerun.

The user guide is [docs/model-source-websocket.md](../../../docs/model-source-websocket.md), linked to the [owning capability](../../specs/model-source-websocket/). No feature README section, changelog edit, environment setting or core navigation item was added.
