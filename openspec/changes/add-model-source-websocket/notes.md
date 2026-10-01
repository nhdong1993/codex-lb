# Review notes

Review scope: the uncommitted native model-source WebSocket implementation
against `HEAD` (`0b229b15`). Unrelated working-tree changes were excluded. This
review did not enable a provider or deploy the application. The user authorized
the original fixes and later explicitly authorized fixing the review findings.
Historical findings below are retained as evidence; the latest correction status
is first.

## Additional review after F23–F24 — 2026-10-01

The requested residual-bug review is complete with **one new P2 finding**,
unresolved. This review covered the current native implementation against
`0b229b15`, not only the two most recent corrections. Application code and tests
were not edited; no commit, deployment or provider enablement occurred.

| ID | Priority/category | Location | Finding | Estimated scope |
| --- | --- | --- | --- | --- |
| F25 | P2 / compatibility | `proxy/api.py:5160–5164` | Extracting the shared ownership-miss helper changed existing HTTP 409 errors from `server_error` to `invalid_request_error` through `source_ws_error`. A continuation whose source was disabled is now classified as invalid client input, including sources whose WebSocket capability is off. | Small envelope-preservation fix and HTTP route regressions |

Reproduction: complete an HTTP source request, disable that source, then send a
continuation with its `previous_response_id`. Both route families and their
trailing-slash equivalents retain `previous_response_owner_unavailable` and
status 409 but return the changed type. **Four current-code cases fail; all four
controls pass** when only `_source_ownership_miss_denial` is restored from HEAD.
Evidence: `/tmp/source-ws-review-after-f24/independent/http-contract-final.log`
and `test_residual.py` in the same directory. The shared helper should preserve
the existing `openai_error` envelope when adapting it to either transport.

The independent review confirmed F25 and reported no additional actionable
findings. Its 10 supplementary isolated checks and 45 mapped tests passed,
covering invalid controls, effective warmup overrides, queued alias changes,
ownership collisions, transport retries, deadlines, heartbeat and admission.
The report is `/tmp/source-ws-review-after-f24/independent.log`.

The parent ran all seven native/transport test files in one process with
isolated SQLite on tmpfs: **284 passed**, one AnyIO deprecation warning,
302.01s. The prior timeout did not recur; its cause remains unproven. This
existing suite does not assert the HTTP error type covered by F25. External
client/provider and PostgreSQL conformance remain open. See
[verification.md](verification.md) for commands and limits.

## F23–F24 corrections — 2026-10-01

The user authorized both P2 findings with “Fix nào”. Both corrections are
implemented locally, with no commit, push, deployment or provider enablement.

| Finding | Correction | Regression coverage |
| --- | --- | --- |
| F23 | Omit allowlisted names without an eligible Responses candidate from the capability map; retain false values for eligible HTTP-only/nonstreaming pools and denial for empty/enforced-ineligible sets | 11 additional installer/catalog cases, all three export platforms, native-route completion and reservation/admission cleanup |
| F24 | Reuse the established WebSocket domain-error formatter during shared preparation and source quota acquisition | 44 cases across both routes and slash variants, initial/reused source sessions and subscription preparation; HTTP envelope controls, error parameters and reservation/admission checks |

Only two application files changed in this correction pass. The source
capability calculation retains its existing candidate ordering, and the error
conversion leaves upstream provider redaction separate. Requirements, design
and stable context were synchronized with these corrections.

The independent review completed with **no actionable findings** in the two
snapshot-scoped changes. Its additional checks covered queued policy/quota
rejection, empty source scope, formatter parameter normalization and provider
redaction: **18 cases passed across two runs**. Initial reviewer quota failures
came from a fixture that ignored the active reservation's refund; correcting
that setup made both cases pass. The report is
`/tmp/source-ws-f23-f24-independent-review.log`; supplementary evidence is in
`/tmp/f23f24-scoped-review/`.

The original 17 reproductions passed across runs. The first combined run had
16 passes and one five-second receive timeout in the native-only control; that
control passed unchanged in isolation. Later parallel mapped runs encountered
SQLite/cleanup timeouts and were interrupted. These runs are retained as
incomplete evidence, not clean passes. The final sequential runs on isolated
SQLite/tmpfs passed **102 focused cases** and **317 mapped compatibility cases**;
19 PowerShell execution cases were skipped because `pwsh` is unavailable.
Whole-repository Ruff/format and all 67 strict main specs passed. Two existing
whole-repository type errors remain outside this pass. Detailed results and
remaining conformance limits are in [verification.md](verification.md).

## Additional review after F21–F22 — 2026-10-01

That review completed with **two new P2 findings**, unresolved at the time and
subsequently corrected above. It was review-only: application code was not
changed, committed or deployed during that review.

| ID | Priority/category | Location | Finding | Estimated scope |
| --- | --- | --- | --- | --- |
| F23 | P2 / compatibility | `model_sources/websocket_capability.py:29,39,56` | Adding every allowlisted name to the capability map turns disabled or Chat-only models with no eligible Responses candidate into `False` entries. `all(models.values())` then disables the entire source-only installer even though every eligible Responses model is native-capable. | Small eligibility correction with installer/route regressions |
| F24 | P2 / compatibility | `proxy/api.py:1374–1375` | `AppError` conversion discards `error_type` and `param`. Revoked keys, model/reasoning denials and exhausted source quota become `invalid_request_error`; reasoning denials lose `param="reasoning.effort"`. The callback also changes subscription-only sessions because it runs before backend selection. | Small envelope-preservation correction with both-route controls |

F23 was reproduced through the actual Linux export, key catalog and native
`/v1/responses` route: Chat-only and disabled-model allowlist variants fail the
installer assertion while the catalog prefers WebSocket and native inference
completes; the native-only control passes (**2 failed, 1 passed**, 14.74s).
Replacing only the exported-policy helper with its pre-F22 snapshot makes all
three cases pass (**3 passed**, 13.40s). Tests and logs are under
`/tmp/source-ws-review-after-f22/{test_discovery_scope.py,discovery-scope.log,discovery-prior-control.log}`.
The correction should exclude names with no eligible Responses candidate while
retaining effective-alias fallback and HTTP-only/nonstreaming eligible peers.

F24 was independently reproduced on both route families for revoked-key,
forbidden-model and forbidden-effort requests (**6 failed**), with **6 passing
controls** that bypass only the new source callback. Two source-quota cases also
fail while their HTTP controls preserve `rate_limit_error`; no provider call or
reservation leak occurs. Evidence:
`/tmp/codex-ws-residual-review/{test_error_contract.py,error-contract.log,quota-error-contract.log}`.
The parent inspected the reproductions and domain-error definitions. The completed
independent report is `/tmp/source-ws-review-after-f22-independent-retry.log`.
Its first launch could not inspect the repository because of a nested sandbox
setup error; that launch is not review evidence. The retry completed successfully.

The complete existing native suite passed **182/182** in one process in 524.67s
with a temporary read-only task-stack probe and one AnyIO deprecation warning:
`/tmp/source-ws-review-after-f22/native.log`. The prior cleanup timeout did not
recur, so its original cause remains unproven; it is not a new confirmed finding.
The new failing reproductions identify gaps outside that existing suite.
Real client/provider and PostgreSQL conformance remain unverified.

## F21–F22 corrections

The user authorized both findings from the completed review in
`/tmp/source-ws-review-after-f20.log` and the parent report
`/tmp/source-ws-review-after-f20-confirmed.md`. Both are now implemented locally:

| Finding | Correction | Regression coverage |
| --- | --- | --- |
| F21 | Preserve the original received byte count and reject an oversized first source create before admission/reservation; retain native reuse limits and subscription ingress | All four route variants; whitespace, UTF-8 and JSON escapes; exactly 16 MiB accepted, larger first/reused input rejected, correction after rejection, zero extra reservations and no admission leak |
| F22 | Share source candidate ordering/permission checks with routing and evaluate catalog/installer capability against the effective model's complete pool | Enforced reasoning/fast aliases, exact source precedence, canonical fallback, fast-mode prohibition, all installer platforms, both route families/slashes, HTTP controls, mixed/non-streaming pools, disabled/unassigned sources and exact allowlists |

The new regressions pass **47 cases**: 40 input/discovery cases, 5 effective-pool
controls and 2 buffered-correction cases. Existing compatibility checks pass
**339 cases, 19 skipped** (PowerShell unavailable), and the focused HTTP source
selection suite passes **22 cases**. Ruff, affected type checks,
timing/cancellation checks and strict OpenSpec validation pass. Whole-repository
type checking retains the same two unrelated existing test diagnostics.
The independent fix review completed with **no actionable findings** and
**29 additional isolated checks passed**. Its report is
`/tmp/source-ws-f21-f22-review.log`.

Combined native verification exposed two fixture problems: a restored instance
method masked subsequent class-level source-pool controls, and the zero-grace
drain assertion did not await tracked deferred settlement. Both fixtures are
corrected; the ordered retry/drain/admission controls pass **20 cases**. A later
combined native run passed all 55 base cases but hit an intermittent five-second
deferred-settlement wait, then was interrupted to inspect the failure (70 passed,
1 failed). All six unchanged variants passed alone; the remaining four native
files subsequently passed **127 cases** in 277.48s. All native cases therefore
have passing evidence, but this is not a clean combined-suite result and the
intermittent timeout's cause remains unresolved. Exact commands, evidence and
final results are in [verification.md](verification.md). No commit, deployment
or production capability change was performed.

## F12–F16 corrections

All five corrections and the four later findings F17–F20 are implemented in the
working tree. Final local checks pass. Independent review terminated with
model/account errors before a final report; no commit or deployment was performed.

| Finding | Correction | Regression coverage |
| --- | --- | --- |
| F16 | Resolve explicit subscription turn-state ownership under the exact API key before source dispatch; preserve unregistered synthesized source placeholders; reject effective previous-response overrides owned by subscription | Both routes, exact/other-key scope, missing/conflicting/unavailable aliases, reused socket and original/effective previous-response owners |
| F12 | Observe active deadlines independently from persistence; close transports, bound scope cleanup and retain late tasks in tracked service cleanup | Acquisition, ownership publication and settlement on both routes; claims and late reservations finish once; successful terminal has no second error |
| F13 | Log a failed reservation touch and retry at later heartbeat intervals with an independent database session | Transient failure and control with simulated seven-hour ledger aging; stale reaper preserves live reservation and success finalizes |
| F14 | Start preparation under session lifecycle ownership; use bounded read-ahead and await reader transfer while preserving raw frames and timestamps | Disconnect, drain, transport cancellation and deadline during lookup; subscription handoff after valid/invalid input; frame/byte bounds and source queue limit |
| F15 | Exclude a lost admission candidate and reselect within five candidates and the original deadline; recheck effective policy/controls/ownership before quota | Portable success, pinned refusal, replacement capability/background denial and deadline on both routes |

The original failing review fixtures now pass: **7 deadline/heartbeat/lookup
cases**, plus **9 admission/ownership cases**. The repository policy matrix
passes **28 cases**. Full-suite checking also found a stale HTTP bridge cleanup
protocol return annotation after the earlier cleanup helper began returning its
tracked task; the protocol now matches that implementation.

Latest independent review log: `/tmp/source-ws-five-fixes-review-final.log`.
The final result and executed checks are recorded in [verification.md](verification.md).

### Additional variants found while checking these corrections

The CLI reviewer reproduced two further cases before its run was interrupted
by an unsupported-model/account error. Both are corrected; its interrupted run
is not a final clean review. A subsequent CLI attempt also failed because no
account supported the replacement model. The existing reviewer and recovered
CLI also terminated with model/account errors. The recovered CLI inspected more
of the current tree and reproduced F19/F20 below, but did not return a completed
review. These failed attempts do not establish a zero-finding result.

| ID | Priority | Finding | Correction and evidence |
| --- | --- | --- | --- |
| F17 | P2 | A successful terminal with reported usage, withheld before any content delivery, was charged after disconnect | Native pre-content cancellation now releases before considering observed usage; HTTP policy and already-delivered content stay intact. Both route families cover normal generation, warmup and a delivered-content control. |
| F18 | P2 | A proved pre-send connection retry could install a replacement turn's longer source deadline over the earlier deadline | Preparation returns the session's earliest deadline to every turn, including connection retries. Both routes verify timeout after a shorter first source fails and a longer replacement connects. |

The original independent reproduction file
`/tmp/test_source_ws_independent_edges.py` now passes **all 3 cases** in 15.12s
(`/tmp/source-ws-independent-edges-parent-final.log`). The first review's raw
output and interrupted session remain available, but neither it nor the failed
replacement CLI invocation counts as completed verification.

### F19 — Do not bind an invalid initial subscription create

The recovered reviewer identified a later validation variant of F2: source
preparation hands an `input_image` file reference to subscription preparation,
which rejects it with `unsupported_input_image_format`. The subscription flag
was set before this validation, so a subsequent valid source create returned
`websocket_reconnect_required` despite no backend having admitted a turn.
The parent independently reproduced both error frames with
`/tmp/test_source_ws_binding_edge.py`.

The flag now becomes true only after subscription preparation and ownership
validation succeed. Four checked-in route cases cover file IDs and sediment
URIs on both routes, a valid source response afterward, and exactly one source
reservation. Existing valid subscription-to-source switch coverage remains.
The focused handoff/backend-switch matrix passed **14 cases** in 56.48s, and
the exact independent reproduction now passes in 3.75s. Ruff, affected type
checks, timing/cancellation and strict OpenSpec validation also pass. The final
subscription suite passes **219 cases** in 259.14s after the fixture correction
described below.

### F20 — Use the Responses stream budget for native source WebSockets

The recovered reviewer then compared the source session deadline with the
Responses compatibility requirement. Native source WebSocket preparation used
the dashboard `proxy_request_budget_seconds` directly, so a 60-second generic
budget could terminate a source turn even though the configured
`http_responses_stream_request_budget_seconds` was 7200 seconds. The source
session now uses the shared stream-budget helper, preserving the source-specific
shorter timeout and the earliest deadline across retries and queued turns.

Both public route families have a Clock-based active-turn regression: the
lifecycle observer checks an active generation after the generic budget elapses,
then the provider completes it within the longer stream budget. Controls verify
that a shorter stream budget still expires the generation and an absent stream
setting uses the dashboard generic budget, with settled/released quota and no
admission leak. Existing lookup/retry tests now configure the stream-specific
budget explicitly.

The final native matrix passed **183 cases** in 399.36s. A separate isolated
control restores the old generic-budget choice through a temporary pytest
plugin: both longer-stream cases then fail with an early error instead of a
completed response (**2 expected failures** in 5.36s). The six budget cases pass
without that control; it does not modify the repository or production settings.

The subscription sequential-turn fixture was also corrected so its first
response batch is released by the first send; the prior fixture queued the
second batch before the second request and could race dispatch-owner capture.
The recovered review reproduced F20 before the CLI failed with
`The 'gpt-5.6-sol' model is not supported when using Codex with a ChatGPT account.`
This is a recorded finding and not a clean zero-finding external review.

## Fix verification and review iterations

The fixes are implemented in the working tree, without a commit or deployment.
After the original fixes, the independent reviewer reran all 33 then-current
regression cases successfully. Existing native routes, adapter and SQLite
migration passed 68 cases; shared HTTP/subscription/dispatch/pool regressions
passed 378 cases. Review iteration 2 nevertheless found two additional variants
of terminal accounting and initial lifecycle ownership, recorded below. Their
fixes and expanded regressions are implemented. The final regression run passed
45 cases and native routes/adapter/migration passed 68 cases again. Iteration 3
completed while the parent session's sandbox was unavailable and found two
further bugs. The user explicitly requested an additional review; that fresh
independent review is complete. It confirms both surviving P2 findings and
three additional defects, for **one P1 and four P2 findings** below. No application
or repository test code was changed during this review. Final results belong in
[verification.md](verification.md).

## Findings from the additional review (before these corrections)

These were the five open findings when the user requested the current fix pass.
Locations and descriptions refer to that pre-fix snapshot. Review reproductions
use an isolated SQLite database and local providers; application and repository
test files were not modified during the review-only pass.

| ID | Priority | Category | Location | Finding | Effort |
| --- | --- | --- | --- | --- | --- |
| F16 | P1 | bug | `app/modules/proxy/api.py:1430-1431` | Source dispatch ignores a proven subscription turn-state owner | medium |
| F12 | P2 | bug | `app/modules/proxy/source_websocket.py:253-265,421-424` | Active deadlines wait indefinitely for cancellation-deferred persistence | medium |
| F13 | P2 | bug | `app/modules/proxy/source_websocket.py:360-368,403-406` | One transient heartbeat error permanently stops reservation refresh | small |
| F14 | P2 | bug | `app/modules/proxy/api.py:1569-1581` | Initial source-policy lookup runs before disconnect/drain lifecycle ownership | medium |
| F15 | P2 | bug | `app/modules/proxy/api.py:1484-1488,1508-1510` | Capability lookup between selection and admission rejects work while an equivalent source is free | small |

### F16 — Preserve subscription turn-state ownership before source dispatch

The new callback resolves subscription ownership through
`_select_responses_model_source_with_continuity()`, which only checks
`previous_response_id`. It does not resolve an explicit `x-codex-turn-state`
against the existing API-key-scoped subscription bridge owner. The source
callback runs before the subscription WebSocket worker's independent turn-state
owner check, so a turn can reach a source despite proven subscription ownership.
The capability-lineage check covers security requirements, not this account
ownership constraint.

The reproduction registers a real durable turn-state alias for a subscription
account, authorizes that account and a source on the same key, and confirms that
`_resolve_compact_turn_state_owner()` returns the account. A create with that
header and no `previous_response_id` nevertheless reaches the local source and
returns `response.created` on both route families. Disabling only the new source
callback prevents both source calls; the legacy guard returns HTTP-required.
This control establishes the new bypass, not a claim that the legacy path can
serve the source model on an account.

The independent reviewer also reproduced this with a `gpt-5.4` source and a
durable subscription owner under the same mixed key. Both anchored requests
reach the source without invoking subscription preparation; controls omitting
the turn-state header correctly use the source. The subscription path is
stubbed locally, so the test cannot contact a real subscription provider.

Resolve hard subscription turn-state ownership before source admission and
preserve the existing owner/conflict/lookup-failure behavior. Keep ordinary
unregistered synthesized source turn-state placeholders working. A request
with a proven subscription owner must remain on its owner path or fail closed,
not silently start a source conversation with its continuity header discarded.

### F12 — Enforce deadlines independently of deferred persistence

`_reserve()` and `_generation()` use `wait_for()`, but quota acquisition,
ownership publication and settlement intentionally defer cancellation until
their persistence completes. The session lifecycle watcher only handles drain
and idle sockets, so no task can close an otherwise active session when its
absolute deadline expires inside that persistence.

The route reproduction configures `timeoutSeconds=1`, blocks each persistence
phase independently, and waits nine seconds. All three cases retain an open
ASGI scope and one admission claim, with zero tracked finalizers. Acquisition
has not contacted the provider; ownership withholds all output; settlement has
already delivered the success terminal. Releasing the blocked operation allows
cleanup. Add a deadline watcher independent of the persistence task and transfer
unfinished finalization into the existing tracked cleanup ownership.

### F13 — Keep reservation heartbeat alive after a transient database error

The native heartbeat has no retry/error handling around its database touch.
One exception permanently ends the task; `_generation()` later gathers and
discards that exception. The subscription heartbeat already handles transient
touch failures and retries. With a source/request budget longer than the
six-hour stale reservation cutoff, the stale reaper can release the live
reservation, causing later successful settlement to become a no-op.

The reproduction configures an eight-hour budget, injects one touch failure,
and simulates elapsed time by aging the isolated ledger row. Only one touch
occurs, the reaper releases the reservation, and the response is logged as
successful. The no-failure control continues touching and finalizes correctly.
Retry recoverable touch failures or terminate the turn rather than silently
continuing without reservation refresh. The long-budget condition is material;
the reproduction does not claim that the default ten-minute request budget
crosses the six-hour cutoff on its own.

### F14 — Start lifecycle ownership before the initial source lookup

The route awaits the initial `prepare()` before starting `session.run()`.
Moving reservation acquisition into the worker fixed the prior F11 case, but
source/policy/ownership reads still occur outside both the downstream reader
and the lifecycle watcher. A blocked initial lookup therefore does not observe
a queued disconnect or expired drain, even when the lookup itself can be
cancelled normally. Its outer timeout is the full request budget.

Blocking `ModelSourcesRepository.list_responses_sources_for_model` and then
disconnecting or expiring drain leaves the ASGI scope open without a close
frame after six seconds in both cases. This differs from F12: no native worker
or active-turn watcher has started, and persistence need not defer cancellation.
Run initial preparation under bounded lifecycle ownership while preserving
recoverable preselection errors and subscription handoff.

### F15 — Retry source selection when admission loses a race

The pool chooses a source from current admission counts, then awaits the
effective-payload capability lineage lookup before claiming its slot. Another
request can occupy the selected source during that database await. The failed
claim immediately returns `503 model_source_busy` instead of selecting another
eligible source. The HTTP choose/claim path has no intervening await.

The route reproduction creates two equivalent capable sources with
`maxConcurrency=1`, pauses the first request's effective capability check after
selection, and starts a second real WebSocket restricted to the chosen source.
On resumption, the first request receives 503 while admission counts are one
and zero. The real selector and bulkhead are unmodified; the test verifies the
capability call has lineage aliases and thus a real database lookup path.
Retry selection within the preparation budget after a failed admission claim,
revalidating the chosen effective payload before reservation. Do not bypass
capability checks or move an owned continuation to another source.

### Current reproduction evidence

```bash
PYTHONPATH=/home/dong01/codex-lb .venv/bin/pytest -p tests.conftest \
  -c pyproject.toml /tmp/test_source_ws_final_review.py -q -s --timeout=60
PYTHONPATH=/home/dong01/codex-lb .venv/bin/pytest -p tests.conftest \
  -c pyproject.toml /tmp/test_source_ws_additional_review.py -q -s --timeout=45
PYTHONPATH=/home/dong01/codex-lb .venv/bin/pytest -p tests.conftest \
  -c pyproject.toml /tmp/test_source_ws_admission_race_review.py -q -s --timeout=45
PYTHONPATH=/home/dong01/codex-lb .venv/bin/pytest -p tests.conftest \
  -c pyproject.toml /tmp/test_source_ws_turn_owner_review.py -q -s --timeout=60
```

The first command produced **4 failed, 1 passed** in 41.75s, confirming F12's
three persistence phases plus F13 and its passing control. The second produced
**2 failed** in 15.93s, confirming F14 during drain and disconnect. The assertions
describe required behavior, so these failures are the reproduced bugs. The
third produced **1 failed** in 4.51s, confirming F15's avoidable busy response.
The fourth produced **2 failed, 2 passed** in 12.03s, confirming F16 on both
routes alongside controls with only the source callback disabled. Logs:
`/tmp/source-ws-additional-known-repros.log` and
`/tmp/source-ws-additional-initial-lookup.log`, plus
`/tmp/source-ws-admission-race-review.log` and
`/tmp/source-ws-turn-owner-review.log`.

The fresh independent reviewer reran the deadline/heartbeat fixture with
**4 failed, 1 passed** in 40.06s (`/tmp/source-ws-fresh-known-repros.log`) and
its separate turn-state fixture with **2 failed, 2 passed** in 12.23s
(`/tmp/test_source_ws_fresh_turn_owner.py`,
`/tmp/source-ws-fresh-turn-owner.log`). The latter controls omit the turn-state
header rather than disabling the callback.

Iteration-3 raw review: `/tmp/codex-lb-source-ws-final-review-20260930.log`.
The additional review's output is
`/tmp/codex-lb-source-ws-additional-review-20260930.log` (completed successfully;
all five open findings confirmed). It also reran the checked-in public-route
regressions: **45 passed**, one AnyIO deprecation warning, in 93.64s. No further
automatic fix/review iteration was started; this user-requested pass was
review-only.

## Previously corrected findings

| Finding | Correction | Route regression coverage |
| --- | --- | --- |
| F7 | Resolve durable capability lineage before raw and effective source dispatch; recheck reused turns and fail closed on lookup failure | Parent/session/turn/previous aliases on both routes, override metadata, reused socket and unavailable lookup |
| F2 | Return separate subscription/handled/closed outcomes; initial validation does not bind or close the socket | Invalid subscription create followed by a valid create on both route families |
| F8 | Close/abort an unusable native upstream before finishing its dispatch and returning admission | Timed-out provider plus blocked downstream error, with `maxConcurrency=1` and a second client |
| F1 | Keep failure precedence and successful terminal handoff through cancellation; handoff starts after acquiring the write lock | Failed terminal with/without usage, successful warmup without usage, withheld ownership publication |
| F6 | Read request-scoped dashboard timeout overrides | Settings API update and actual idle closure |
| F4 | Use effective forced-model policy and the ordinary source selector for the handshake exemption | Both route handshakes with/without an enforced subscription model |
| F3 | Classify recognized continuity failures before sanitizing messages | Reconnect on native/public routes, including nested, flat and failed-response envelopes |
| F5 | Bound retry preparation by time remaining from original receipt | Stalled second candidate after a proven pre-send failure |
| F9 | Close transports independently, cap the scope's cleanup wait and retain unfinished settlement in tracked service cleanup | Expired drain and disconnect while settlement stalls; scope exits, then one finalization completes |
| F10 (iteration 2, P1) | Preserve terminal accounting if a downstream send times out or raises a connection error after handoff; close without a contradictory second error | Successful completion and warmup, failed terminal with/without usage, crossed with disconnect/timeout/write failure |
| F11 (iteration 2, P2) | Move quota acquisition into the owned session worker; retain a late acquisition result for exactly one release under tracked cleanup | Drain and disconnect during first acquisition, no provider connection, released reservation and admission after persistence resumes |

Executable regressions are in
`tests/integration/test_model_source_websocket_review.py`; temporary reproductions
below describe the initial failures and are not the final acceptance suite.

Iteration 2 raw output is `/tmp/codex-lb-source-ws-rereview-20260930.log`.
The temporary fixture `/tmp/test_source_ws_iteration2.py` reproduced both bugs:
two terminal timeout variants released quota after success, and expired drain
left first reservation acquisition untracked with the ASGI scope open after
5.5 seconds. The corrected acquisition reproduction passed; repository tests
add disconnect coverage and await retained cleanup before database teardown.

The earlier passing checks in [verification.md](verification.md) do not cover
the failing cases below. The change remains unready for archive or production
enablement. Relevant contracts are the [source WebSocket
requirements](../../specs/model-source-websocket/spec.md), [Responses
compatibility requirements](../../specs/responses-api-compat/spec.md), and
[change design](design.md).

## Confirmed findings

Line references identify the reviewed working tree and can move during fixes.

| ID | Severity | Category | Location | Finding | Effort |
| --- | --- | --- | --- | --- | --- |
| F7 | High | security | `app/modules/proxy/api.py:1375-1383` | Source dispatch skips inherited required-capability routing | medium |
| F2 | High | compatibility | `app/modules/proxy/api.py:1541-1545` | An invalid first subscription create closes the socket even with source WS unused | medium |
| F8 | High | bug | `app/modules/proxy/source_websocket.py:287-290,398-414` | Timed-out generations release admission before closing their upstream | medium |
| F1 | High | bug | `app/modules/proxy/source_websocket.py:306-312` | Cancellation discards an already observed terminal outcome and settles the wrong quota result | medium |
| F6 | Medium | bug | `app/modules/proxy/api.py:1332-1333` | Native source sessions ignore the dashboard timeout overrides | small |
| F4 | Medium | compatibility | `app/modules/proxy/api.py:9439-9447` | Handshake capability detection ignores the key's enforced model | small |
| F3 | Medium | compatibility | `app/modules/proxy/source_websocket.py:237-252` | Generic error sanitization removes the continuity recovery code | medium |
| F5 | Medium | bug | `app/modules/proxy/source_websocket.py:349-351` | Retry preparation runs outside the absolute request deadline | small |
| F9 | Medium | bug | `app/modules/proxy/source_websocket.py:407-414` | Stalled settlement prevents socket closure beyond the HA drain deadline | medium |

### F7 — Resolve inherited capability requirements before source dispatch

The new source callback checks only explicit capability signals with
`parse_routing_intent`. It can dispatch before the subscription preparation
calls `CapabilityRouter.route`, which also reads durable requirements inherited
through parent-thread, session, turn-state and previous-response aliases.

An independent route reproduction first records a `trusted_cyber` requirement
for a parent task under the same API key, then sends an ordinary source create
carrying that parent ID without repeating the explicit capability header. The
durable router confirms the requirement, but the provider receives the request
and returns `response.created`. A separate control disables only the new source
callback: the old path returns an error and makes no source call.

This bypasses the routing restriction for inherited security work. It does not
require a forged credential or access to another key. The source WebSocket
contract explicitly retains required-capability precedence.

Suggested fix: resolve effective capability intent, including durable lineage,
before source selection or reservation. Required work must remain on the
authorized capability path, and lineage lookup errors must fail closed. Apply
the check to initial and queued turns without disturbing the active turn's
reservation. Cover inherited aliases and lineage-store failure at the routes.

### F1 — Preserve terminal classification during cancellation

The parser records the terminal before downstream delivery. If the client
disconnects while that delivery is unwinding, `_generation` finalizes the
dispatch as `cancelled` regardless of `event_usage.terminal_kind`.
`SourceDispatch.settle_or_release` then charges a failed response when it has
usage or previously delivered content. Conversely, a successful `generate:false`
warmup without usage releases its reservation instead of settling input usage.

A deterministic route reproduction holds the ASGI send after exposing the
terminal, then disconnects the client. Both `response.failed` variants (with
usage and with only prior content) produce a `finalized` reservation and a
`cancelled/client_disconnected` log; they should release as errors. The successful
warmup instead produces a `released` reservation and a cancelled log.

Suggested fix: retain the upstream terminal and the downstream delivery outcome
through cancellation, using the same settlement rules as the HTTP
`settlement_stream` cancellation branch. Preserve failure precedence and the
distinction between successful delivery and withheld output. Cover both billing
directions at the route boundary.

### F2 — Keep recoverable subscription validation errors recoverable

The new source callback runs before subscription request preparation for every
`response.create`. Normalization can fail before determining whether the model
belongs to a source. The catch at `api.py:1541` sends an error and closes any
socket whose first subscription request has not yet bound it.

Reproduction: with no model source configured, send an initial subscription
create with `input: 42`, then a corrected create on the same `/v1/responses`
socket. The first error is followed by `websocket.close`; the corrected request
never reaches the subscription upstream. Disabling only the new callback in
the same test restores `response.created` for the corrected create. The existing
subscription loop explicitly continues after this validation error.

Suggested fix: distinguish a recoverable routing/prevalidation error from a
terminal source-session result. Do not close or claim an unbound subscription
socket solely because shared normalization rejected one create.

### F3 — Preserve sanitized continuity classification

Every source `error` or `response.failed` becomes
`model_source_response_failed`. This also rewrites a provider's
`previous_response_not_found` after reconnect, hiding the stale-anchor
classification required by the existing route contracts and this change's
continuity design.

Reproduction: complete a response, close the socket, reconnect to its durable
source owner with `previous_response_id`, and have that provider reject its
missing connection-local state. Both routes emit generic 502 errors. The
Codex-native route should expose sanitized `previous_response_not_found`; the
public route should expose `stream_incomplete`. No cross-source retry is needed
or authorized.

Suggested fix: classify recognized continuity failures before generic
redaction, reusing the existing safe route-specific error fields. Never expose
the raw provider message, missing response ID or endpoint. Add reconnect tests
for both route families.

### F4 — Apply enforced-model policy before bypassing handshake fallback

During a recent subscription WebSocket failure, the handshake probe accepts
when it finds any assigned capable source matching `allowed_models`. It never
applies `enforced_model`. A key forced to subscription model `gpt-5.4` therefore
upgrades because an assigned source offers an unrelated `source-ws-model`, even
though enforcement prevents this key from routing any create to that source.

Both actual ASGI route handshakes return `websocket.accept` in this case instead
of the required HTTP 426. After upgrade, the existing handshake-based HTTP
fallback is unavailable. Control cases without the enforced model correctly
accept on both routes.

Suggested fix: evaluate source eligibility under effective key model policy
before exempting the handshake from the subscription failure marker. Preserve
the exemption for keys that can actually reach a capable source.

### F5 — Bound preparation of a retry candidate

Initial and queued preparation use `scheduler.wait_for`, but preparation after
a proven pre-send connection failure awaits `self.prepare` directly. A stalled
policy/ownership/source lookup can therefore outlive the request budget; the
session lifecycle does not enforce idle expiry while the worker is active.

Reproduction: use two eligible sources, fail the first connection before send,
and hold the second candidate lookup. With a 0.25-second request budget, the
route still has no timeout response after one second. The test subsequently
disconnects and awaits cleanup; it does not contact an external provider.

Suggested fix: wrap retry preparation in the remaining absolute request budget
and translate expiry into the normal source timeout envelope. Preserve the
existing reservation ownership and cancellation-deferral cleanup.

### F6 — Apply dashboard timeout overrides to the native session

The source entry point reads bare environment settings. The subscription
service and HTTP source paths apply `with_dashboard_overrides`, but the new
source session uses the environment's request, connect and downstream idle
timeouts even when the dashboard has persisted different values.

Reproduction: set `proxyRequestBudgetSeconds: 900`,
`upstreamConnectTimeoutSeconds: 16` and
`proxyDownstreamWebsocketIdleTimeoutSeconds: 0.25` through `/api/settings`, then
complete a native source response on `/v1/responses`. The session receives
`600`, `8` and `120` respectively, and remains open after the configured idle
timeout. This prevents operators from controlling these source sessions with
the existing timeout settings.

Suggested fix: apply the request-bound dashboard overlay before obtaining the
three timeout values. Verify actual source session behavior after a settings
API update; environment-only monkeypatches cannot catch this regression.

### F8 — Retire a failed generation's upstream before releasing its slot

`_generation` finalizes a timed-out dispatch, which releases quota and source
admission. `SourceDispatch.close_source()` does not own the native connection;
the actual close happens later in `run` cleanup, after error delivery and task
settlement. Downstream backpressure can therefore leave the upstream generation
running after its admission slot has become available.

An independent local-provider reproduction configures `maxConcurrency: 1`,
stalls the first generation until its first-frame timeout, and blocks downstream
error delivery. At that point the source bulkhead reports zero while the first
upstream is still open. A second client is admitted and sends another generation:
the provider observes two outstanding generations. The parent reviewer reran
the reproduction and confirmed the same failure.

Suggested fix: transfer explicit native transport cleanup ownership to the
failed attempt or close the session's upstream before releasing that attempt's
claims. Preserve healthy connection reuse only after a real terminal outcome.
Error delivery and slow settlement must not delay retirement of a failed
transport. Verify timeout plus slow-client behavior against the actual source
concurrency limit.

### F9 — Bound socket teardown independently of settlement

Session cleanup cancels all tasks, then awaits an unbounded `gather` before
closing either socket. A worker already finalizing quota defers cancellation
until persistence completes. If that persistence stalls, neither transport
closes and the ASGI scope remains in flight even after HA drain has expired.

The independent reproduction blocks the settlement write after a completed
response, expires drain immediately, and checks both transports after more than
two lifecycle polling intervals. Both remain open until settlement is manually
released. The parent reviewer reran the same route fixture and confirmed it.
This is distinct from F8: it occurs even after a successful terminal and concerns
bounded teardown while accounting still owns cleanup work.

Suggested fix: close transports within their cleanup budgets before waiting
on shielded persistence, then apply the existing finalizer/deferred-cleanup
ownership mechanism to any unfinished accounting task. Do not abandon the
reservation or simply cancel its database operation. Cover slow settlement
during both client disconnect and expired drain.

## Reproduction evidence

Temporary review fixtures are in `/tmp/test_source_ws_review.py`; they do not
modify repository tests or use production data. They use `tests.conftest`'s
isolated SQLite database and local aiohttp WebSocket providers or explicit
subscription/connection seams. Assertions describe the intended behavior and
therefore fail where the reviewed code contains a bug.

```bash
PYTHONPATH=/home/dong01/codex-lb .venv/bin/pytest \
  -p tests.conftest -c pyproject.toml /tmp/test_source_ws_review.py \
  -q -s --timeout=90 --junitxml=/tmp/source-ws-review-reproductions.xml
```

Result: **10 failed, 3 passed** in 29.25 seconds. The failures represent five
distinct findings, not ten distinct bugs: F1 has three failing variants; F2 has
one failure and one control; F3 has two route failures; F4 has one helper failure,
two route failures and two passing route controls; F5 has one deadline failure.
Output is in `/tmp/source-ws-review-reproductions.log`.

An additional focused run of
`test_review_dashboard_timeouts_apply_to_source_session` confirms F6:
**1 failed, 13 deselected** in 4.57 seconds. Its output is in
`/tmp/source-ws-review-dashboard-timeouts.log`. Across these non-overlapping
executed cases, the review has 11 failing assertions and three passing controls
covering six distinct findings.

F7 was reproduced independently and then checked with a callback-disabled
control in `test_review_inherited_capability_enforced_before_source`:
**1 failed, 1 passed, 14 deselected** in 6.64 seconds. The output is in
`/tmp/source-ws-review-inherited-capability.log`. Including that additional
pair, the manual review executed 12 failing cases and four passing controls
across seven distinct findings.

F8's independent fixture is in `/tmp/review_native_source_ws.py`; the parent
review reran `test_timed_out_source_closes_before_admission_release` with
**1 failed, 8 deselected** in 3.83 seconds. Output is in
`/tmp/source-ws-review-timeout-close.log`. The parent-reviewed reproductions now
cover eight findings with 13 failing cases and four passing controls; repeated
independent executions are not included in that count.

The independent reviewer also reran the checked-in native route, adapter and
migration suites: **68 passed, one warning** in 181.92 seconds. That passing
suite does not include these review reproductions.

F9's `test_drain_closes_transport_while_settlement_is_blocked` was independently
reproduced and rerun by the parent reviewer, with output in
`/tmp/source-ws-review-drain-close.log`. Together, the parent-reviewed
reproductions cover **nine findings**: **four High and five Medium**. Each has
at least one failing route reproduction; four passing controls isolate the
subscription, handshake and inherited-capability regressions.

## Initial independent reviewer evidence (historical)

The first `codex-review-loop` invocation could not inspect the repository because
its nested sandbox failed with `bwrap: loopback: Failed RTM_NEWADDR: Operation
not permitted`. It returned no correctness evidence. A second invocation used
the execution policy already provided to this workspace, successfully inspected
the scoped diff, and completed on 2026-09-30.

Its seven findings correspond to F1, F3, F4, F6, F7, F8 and F9 above. F2 and F5
were found by the parent review. The independent reviewer confirmed eight
additional failing fixture cases (including two F1 variants) and 68 passing
existing tests. Repeated executions and overlapping cases must not be summed as
distinct bugs. A latency-only observation was excluded because the shared
source HTTP behavior does not establish a new timing contract here.

Raw independent output: `/tmp/codex-lb-source-ws-review-20260930-retry.log`.
Independent fixture: `/tmp/review_native_source_ws.py`; combined output:
`/tmp/review_native_source_ws_confirmed.out`. At the time of that initial report,
no application/test fixes or commits had been made. The user subsequently
authorized the fixes summarized above, including the later F12–F16 corrections.
