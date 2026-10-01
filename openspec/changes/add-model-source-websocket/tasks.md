## 1. Protocol and client compatibility evidence

- [x] 1.1 Create a deterministic local Responses WebSocket provider fixture covering create, tool continuation, `generate:false`, terminal errors and disconnects; verify a direct client can complete two turns over one upstream socket.
- [ ] 1.2 Exercise the intended client against handshake 426 and accepted-socket source errors, including source-only/mixed assignments and socket reuse; record observed fallback behavior and excluded protocol controls in change context.
- [ ] 1.3 Record the intended provider's endpoint/auth/profile compatibility in a staging conformance report before enabling it; verify HTTP “streaming” is not taken as proof of native WS support and document any failed profile requirement.
- [x] 1.4 Reconcile the current installer, overflow and timeout changes with this plan and divide implementation into focused reviewable PRs, targeting one concern and the repository's approximate 800-net-line limit per PR; verify dependencies are recorded and no intermediate PR advertises unavailable support.

## 2. Capability persistence and management contract

- [ ] 2.1 Add the default-false source capability on the current Alembic parent and model; verify one migration head, upgrade/backfill, downgrade/upgrade and existing-row behavior on supported databases.
- [x] 2.2 Extend source create/read/PATCH validation and persistence, including merged-state Responses dependency and omitted-field behavior; verify management API round trips and unchanged existing capabilities.

## 3. Share source preparation and attempt ownership

- [x] 3.1 Extract source route resolution and candidate payload preparation from HTTP handlers, preserving raw/enforced aliases, original reasoning effort, per-candidate overrides and original/effective ownership checks; verify existing public HTTP pool, payload, file and ownership regressions pass unchanged.
- [x] 3.2 Generalize source dispatch metadata and transport labels while separating turn finalization from session socket closure; verify admission-before-reservation, missing-usage estimates, delivered-content cancellation and idempotent partial-failure cleanup with existing HTTP tests.
- [x] 3.3 Add structured event observation shared by SSE and WS ownership/usage processing; verify response/item/call/encrypted/hosted-resource publication precedes delivery and publication failure withholds the affected event.

## 4. Native source WebSocket adapter

- [x] 4.1 Implement source endpoint scheme conversion and credential-safe native handshake with bounded budgets and no redirects; verify custom path prefixes, absent/configured source credentials, header stripping, environment-proxy behavior and redacted failures against the fixture.
- [x] 4.2 Implement the supported JSON event profile and shared alias/payload shaping; verify instructions, reasoning efforts, tools, field presence, effective `generate:false` warmup (zero/missing usage and unexpected content), malformed/binary/oversize input and rejection of excluded controls/background mode without terminating an unrelated active generation.
- [x] 4.3 Implement per-generation timing, bounded buffers, serialized writes and single-reader ownership; verify slow consumers, eventless/partial disconnects, missing terminal, idle closure and cleanup cancellation with deterministic clocks where applicable.

## 5. Public routing, session lifecycle and source pool

- [x] 5.1 Select source/subscription routing before subscription-only transforms or quota reservation on both public paths and slash equivalents; verify aliases, disabled/incapable sources, forced models, lookup outages, file/subscription pins, compaction and required-capability precedence through actual WebSocket routes.
- [x] 5.2 Integrate a source session owner into initial and subsequent create handling, with one active and one queued turn and immutable upstream identity; verify two-turn tool loops, immediate-after-terminal creates, queue deadline/dequeue revalidation, excess queue rejection and reconnect-required backend/model changes.
- [x] 5.3 Revalidate key revocation/assignment and source enablement/capability/revision between turns and after queueing; verify no later frame reaches a disabled, unauthorized or replaced credential while previously admitted cleanup still completes.
- [x] 5.4 Apply source-pool selection only to eligible native candidates and bounded pre-send retries; verify 401/403/429/5xx handshake rejection policy, connection failure versus ambiguous send, cooldown ordering, exhausted/saturated pools and no replay after send/content or owned continuation.
- [ ] 5.5 Keep explicit global HTTP denial and isolate subscription/source failure state, accounting for a model unknown at handshake time; verify source-only/mixed/account-only scopes and actual-client behavior recorded in 1.2.
- [x] 5.6 Preserve source ownership on HTTP→WS, WS→HTTP and cross-replica reconnect; verify conflicting/unknown/expired owner references, override-introduced references, publication failure and missing upstream connection-local state without automatic anchor removal.
- [x] 5.7 Integrate bounded shutdown/drain and source WS request-log attribution; verify idle/active drain, grace expiry, disconnect during open/first frame/settlement, no orphan tasks, no shared concurrent AsyncSession and no leaked/doubled reservations or admission claims.

## 6. Dashboard, catalog and installer activation

- [x] 6.1 Add the capability control to the existing Model Sources form with API schemas, translations and field validation; verify create/edit persistence and capture before/after screenshots.
- [x] 6.2 Advertise conservative key-scoped source WS model preference after the complete runtime is available; verify source flags, mixed-capability equivalent pools, global policy and absence of leaked source/alias metadata.
- [x] 6.3 Reconcile the installer delta with `disable-install-websockets-only-for-source-assignments`; verify all-capable source-only keys enable WS, HTTP-only/mixed-capability source-only keys retain HTTP, old exports retain their frozen flag, new exports reevaluate policy, other key classes retain their policy, and macOS/Linux/Windows exports remain credential-safe.

## 7. End-to-end verification and documentation

- [x] 7.1 Run the complete route acceptance matrix with a limited key and real local upstream fixture: both routes/slashes, first/reused connection, source capability off/on, concurrent sessions, file/security precedence, retry boundaries and all terminal/cancellation settlement cases; attach results to a verification document.
- [x] 7.2 Run focused existing source HTTP, subscription WebSocket, pool safety, source ownership/history, timing/cancellation, migration and installer/frontend regressions plus affected lint/type checks; record exact commands, results and pre-existing failures separately.
- [x] 7.3 Document opt-in, supported protocol subset, HTTP-only behavior, reconnect limits, mixed-key fallback and HA rollout order under OpenSpec context and linked user docs; verify no feature README/CHANGELOG edits and all user-facing feature pages link to their owning spec.
- [ ] 7.4 Run strict change validation and `openspec validate --specs --strict`, verify implementation against every scenario, and only then sync stable specs/context and archive; for future PR readiness also verify actual current-head GitHub gates and required screenshots.

## 8. Review corrections

- [x] 8.1 Fix inherited capability enforcement, recoverable initial validation and effective-model handshake eligibility; cover initial/reused routes and fail-closed lineage lookup.
- [x] 8.2 Preserve terminal accounting during disconnect and sanitized stale-anchor recovery codes on both route families; cover failures, successful warmup and withheld ownership publication.
- [x] 8.3 Apply dashboard timeout overrides and bound retry preparation by the original request deadline.
- [x] 8.4 Close unusable upstreams before releasing admission and bound session teardown independently of settlement; retain tracked ownership of unfinished cleanup and prove disconnect/drain settlement completes exactly once.
- [x] 8.5 Run regression reproductions, affected suites and strict checks, then complete another independent review and record its findings and disposition.
- [x] 8.6 Preserve exact-key subscription turn-state ownership before source dispatch (F16); cover both routes, lookup failure/conflicts, and ordinary source reconnect placeholders.
- [x] 8.7 Observe disconnect, drain and active deadlines independently from initial preparation and cancellation-deferred persistence (F12/F14); preserve buffered input, subscription handoff, terminal accounting and tracked late cleanup.
- [x] 8.8 Recover native reservation heartbeats after transient database failures (F13); prove an active reservation survives simulated stale reaping and settles once.
- [x] 8.9 Reselect an eligible source after admission loses a race (F15), within the original budget and without moving an owned continuation; recheck replacement policy before quota reservation.
- [x] 8.10 Run new route regressions, affected source/subscription suites, lint/type/timing/cancellation and strict OpenSpec checks; complete an independent review of these corrections and record the disposition.
- [x] 8.11 Correct the independent review's withheld-terminal usage and pre-send retry deadline variants; verify actual-route quota release before delivery, charging after delivery, and the earliest generation deadline across connection retries.
- [x] 8.12 Preserve an unbound socket when subscription-only validation rejects the first create; bind only after subscription preparation succeeds and verify a corrected source create on both routes.
- [x] 8.13 Use the Responses stream-specific request budget for native source WebSocket deadlines; cover active turns after the generic proxy budget and retain the earliest deadline across source retries.
- [x] 8.14 Enforce the native 16-MiB UTF-8 input limit on the first source create as well as reused creates before admission/reservation; retain larger subscription ingress and cover route/slash variants, byte boundaries and correction after rejection (F21).
- [x] 8.15 Resolve advertised source WebSocket capability using effective model aliases, exact source precedence, key scope and fast-mode policy; cover installer platforms, catalogs, capable and HTTP-only effective sources, mixed pools and actual routed requests (F22).
- [x] 8.16 Run F21/F22 reproductions and affected regressions, lint/type and strict spec checks, then independently review the fixes and record the final disposition.
- [x] 8.17 Exclude allowlisted names with no eligible Responses source from the installer capability aggregate; preserve aliases, model enforcement, empty-set denial and mixed eligible pools, with actual export/catalog/native-route regressions (F23).
- [x] 8.18 Preserve domain error status, type, code, message and parameter during source preparation and quota reservation; cover both WebSocket route families/slash variants, source/subscription requests, initial/reused turns and unchanged HTTP controls (F24).
- [x] 8.19 Run F23/F24 reproductions and mapped regressions, lint/type/timing/cancellation and strict OpenSpec checks; independently review the corrections and record the disposition.

## Verification status

Implementation and local acceptance evidence are in [verification.md](verification.md). Open checkboxes retain their original acceptance gates: 1.2/1.3 require the intended client/provider; 2.1 has passed SQLite upgrade/backfill/downgrade/schema checks but PostgreSQL execution remains; 5.5 has passed local routing/failure isolation checks but depends on the client evidence in 1.2; 7.4 has passed strict validation and spec/context sync, while final conformance, archive and any future PR cloud gates remain.

Task 1.4 is satisfied by the dependency-ordered review slices recorded in context; no PR publication is implied. Existing unrelated workspace changes are outside this change.

Task 8.5 records the completed additional review. The user subsequently
authorized all five F12–F16 corrections (**1 P1, 4 P2**), now implemented under
8.6–8.9. F17–F20 corrections are implemented under 8.11–8.13. Local verification
passes (183 native and 219 subscription cases). A later independent review
completed and confirmed F22; the parent also reproduced F21. The user authorized
both corrections, now completed under 8.14–8.16 with 47 new regressions passing
and no actionable findings in the independent fix review. Mapped compatibility
checks passed. Native verification found and corrected two fixture issues;
all native cases passed across runs, but one combined-run cleanup timeout remains
documented for further investigation before archive. These checkboxes record
completed execution and disposition, not a fully clean combined suite or release
approval. See [notes.md](notes.md) and [verification.md](verification.md).

F23/F24 were subsequently authorized and corrected under 8.17–8.19. Final
sequential verification passed 102 focused cases and 317 mapped compatibility
cases, with 19 PowerShell cases skipped because `pwsh` is unavailable. The
independent correction review returned no actionable findings. These runs used
isolated SQLite on tmpfs after interrupted disk-backed runs encountered timeouts;
the earlier timeout cause remains unproven. Whole-repository type checking still
reports two pre-existing test errors outside this pass. All 40 local tasks are
complete; the five original external conformance/release gates remain open.
