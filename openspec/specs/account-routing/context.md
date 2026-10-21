# Account Routing Context

## Purpose

The normative routing contract is in [spec.md](spec.md). This context explains
why transient health is replica-local and how drained accounts return to normal
routing without becoming permanently invisible behind healthier accounts.

## Reauthentication warning state

This fork quarantines `reauth_required` accounts regardless of access-token
expiry, including foreground selection and reuse of already-open bridges.
Operator reauthentication or import repairs the account before it can serve
again. Movable soft affinity can fail over; hard account-owned continuity stays
fail-closed. This deliberately differs from upstream's unexpired-token policy.
Paused, deactivated, deleted, and security-ineligible accounts retain their
hard exclusions. Beta.5 overload isolation and quota recovery do not relax this
fork-specific rule; the normative contract remains in [spec.md](spec.md).

## Replica-local soft health

Error counts, backoff, health tiers, and probe streaks are advisory signals.
They deliberately stay in memory: a different replica may have observed a
different network path, and persisted `status`, `reset_at`, and `blocked_at`
remain the authoritative cross-replica gates.

An account moves from draining to probing only after the fixed quiet period.
Probing is validation, not a permanent low-priority state. Health-tier-aware
selection therefore gives the oldest due probing account one bounded admission
opportunity when healthy accounts would otherwise mask it. The existing
selection timestamp supplies the cadence and fair ordering. Unbound and fallback
sticky selection reversibly reserve that timestamp under the runtime lock before
sticky database work, preventing concurrent requests from consuming the same
interval. The reservation carries both that timestamp token and the runtime
version it observed. Both must still match before the final lease and after
selection-state persistence; otherwise the request releases the reservation and
retries from the newer health state. Sticky selection returns one provisional
desired-state mutation instead of writing during selection. The caller applies
it only after cap classification, lease admission, state persistence, and the
probe CAS; a stale probing snapshot or fail-closed cap result therefore cannot
delete or replace the current owner. A successful rebind collapses the former
delete-plus-upsert sequence into one atomic upsert. Reserve/release remains separate from the
health-observation version used by Force Probe settlement. Recovery therefore
needs no scheduler, random sampling, or operator setting.

## Constraints and failure modes

- Eligibility, quota, cooldown, model, security, and local concurrency-cap
  checks still precede health-tier choice.
- A selectable sticky owner is retained; probing recovery uses unbound or
  fallback selection rather than moving an established owner.
- Hard-sticky fail-closed ownership does not let saturated fallback accounts
  bypass local concurrency caps. Saturated otherwise-available fallbacks return
  the stable local cap reason even when another under-cap fallback is unusable.
  Availability is compared over complete pre-cap and post-cap pools because
  opportunistic eligibility depends on what other foreground capacity exists;
  once a local cap reason is established, opportunistic error translation does
  not replace it. Nor can the post-cap selector revive an under-cap account that
  remains only a transient-backoff fallback.
- A lease race, stale persistence snapshot, or other local selection failure
  releases the provisional timestamp. After selection successfully returns a
  probe, a later caller cancellation may still postpone the next attempt by one
  quiet interval; that conservative bound cannot starve the account permanently.
- A planned sticky mutation runs after admission commits. If that database write
  fails, the request releases its local lease but retains the committed selection
  timestamp; attempting to decrement the shared runtime version would make
  concurrent health settlement ambiguous.
- A failed real request can drain the account again through the ordinary error
  path. Recovery never permits replay after downstream output is visible.
- Restarting a replica clears advisory health as before; persisted account
  status is unchanged.

## Example

Accounts A and B are healthy while C is probing after an upstream incident.
C's last selection is older than the quiet interval, so the next unbound
health-tier-aware selection admits C once. Existing sessions on A and B stay in
place. Budget and account routing-policy preferences cannot mask this bounded
recovery pass. A successful request advances C's local probe streak; C is not due for
another bounded admission until the interval elapses. Three successful
observations restore healthy routing, while an intervening failure restarts
recovery.

## Operational notes

The dashboard Force Probe action can accelerate validation on the replica that
handles the operator request. Only an accepted 2xx probe contributes to local
recovery; operators should inspect `probe_status_code` when an account remains
unused. Non-2xx results, persistent quota exhaustion, and high usage correctly
keep the account out of healthy routing. Successful settlement reloads standard
usage and applies the same weekly/monthly and zero-primary-capacity normalization
as ordinary selection, so plan-specific windows cannot be omitted, mistaken for
short windows, or evaluated for a quota the plan does not have.
Settlement is discarded if newer replica-local runtime activity arrives while
that snapshot is loading, preventing an older probe success from clearing a
later failure.

## Beta.5 overload isolation and evidence-gated quota recovery

Repeated overload rejection escalates from soft backoff to replica-local
isolation, even with intermittent successes. Isolation defaults to 1,800 seconds;
zero disables that escalation. Weighted strategies also discount recent
account-attributable errors after sufficient evidence, without changing
deterministic strategies or hard continuity. These two upstream settings retain
working defaults and allow targeted operator diagnosis without changing the
fork's memory profile or HA topology.

The same window accepts `server_error` only when the upstream message matches
OpenAI's processing-error/help-center signature. For example, “An error occurred
while processing your request. You can retry your request, or contact us through
our help center at help.openai.com if the error persists.” counts, including an
optional following request ID; “Internal server error” or a bare domain mention
does not. Matching ignores case/whitespace and accepts the HTTPS help-center URL.
This narrow signature addresses repeated upstream failures without treating all
local or transport server errors as isolation evidence. If OpenAI changes the
wording, unmatched errors retain generic transient handling until the signature
is updated from observed evidence. Existing health eligibility and API-key
settlement ordering still apply; errors after visible text are not newly penalized.
Terminal failures now explicitly await confirmed API-key settlement before their
health write, including when the chat startup probe closes the stream early.
Counters remain replica-local, and isolation remains a soft routing preference
with the existing hard-continuity and single-candidate protections; it does not
persist an operator PAUSED status. See [spec.md](spec.md).

The integration additionally includes upstream #2078. A new usage sample is not
proof that quota recovered: applicable windows must actually have capacity.
For example, a two-hour upstream 429 followed by primary usage at 100% and weekly
usage at 40% keeps its hold rather than oscillating back to ACTIVE. Only the
marking replica may recover early from valid post-block evidence; peers honor
the persisted deadline or later persisted recovery. Historical or same-second
credit evidence cannot undo an explicit quota block. Ordinary deadline expiry
and the client's upstream error classification are unchanged.

During a later mixed-version rollout, old replicas can still execute the old
early-recovery policy. Schema compatibility is not proof that every replica has
the new evidence gate; verify all serving images after rollout. See [spec.md](spec.md)
and the `treat-usage-limit-as-quota-exhaustion` change for the precise scenarios.

## Code-less burst 429 admission signal (2026-09-10)

A code-less upstream HTTP 429 indicates short-lived account saturation, not confirmed quota exhaustion. A separate local burst deadline steers fresh movable traffic away for 5–30 seconds (upstream Retry-After is bounded), without changing persisted account status, normal cooldown, or the overload-isolation window. For example, fresh traffic prefers B while A is bursting, but an established sticky/file/response owner on A is retained. A single eligible account remains usable.

The burst signal is recorded immediately even for keyed streams; account-health penalties still use their existing settlement ordering, and deferred writes do not restart a completed burst cooldown. Restarting a replica clears the advisory signal; other replicas may have different evidence. No operator setting or schema change is introduced. Coded rate-limit and quota errors retain their existing handling. See [spec.md](spec.md).

## Accounts plan filter and quick routing

The Accounts plan filter is derived from stored plan values in the loaded summaries. It combines with search and status, resets overview pagination, and stays selected when switching Detail/List/Grid. It does not send upstream requests. For example, selecting Prolite and Active limits all three views to active Prolite accounts.

List rows have independent native buttons for management, Burn First and subscription refresh. The flame button shows whether `burn_first` is saved; enabling it sets `burn_first`, and disabling it sets `normal`. Enabling it from `preserve` intentionally replaces that policy. Read-only viewers and requests already pending cannot activate the toggle; reauthentication-required and deactivated accounts remain disabled. A failed update preserves the displayed saved policy and reports the existing mutation error.

Plan badges share the request-log palette: Plus emerald, Team sky, Pro violet, Prolite amber and Promax fuchsia. Unrecognized values keep their label with a neutral badge. These styles do not change plan capacity or routing eligibility.

## Model entitlement rejection while a plan is stale

The exact “model is not supported when using Codex with a ChatGPT account” error now requests shared priority verification from HTTP streaming and WebSocket error paths, including successful failover paths. Shared evidence temporarily excludes the latest rejected account/model pair until the original two-minute request window expires. Repeat errors do not prolong the deadline; only the latest rejected model is retained to bound storage. Model rejection alone is not evidence of Free or revoked credentials and does not add an account-health penalty.

For example, when A rejects model M, a movable request for M can use B while another model remains eligible on A. File and conversation ownership still resolve to A; its temporary unavailability fails closed under the existing contract instead of transferring ownership to B. Matching credential lineage is required for exclusion, and reauthentication/import discards old work. Usage-confirmed plan changes invalidate selection caches so catalog filtering can apply the current plan.

Direct WebSocket sessions also check this shared account/model evidence when a new turn would reuse an open upstream connection, then recheck after admission waits before sending. An idle movable turn retires the excluded socket and re-enters selection; a hard file or conversation owner remains pinned and fails closed. A newly excluded turn cannot retire a socket that still carries another accepted turn: only the unsent turn is rejected and its admission resources are released. For example, a rejection recorded on replica B now prevents replica A's existing idle socket from sending another request for that same model. Unrelated models and expired evidence leave reuse available.

## Model admission on reused transports

Direct WebSocket dispatch performs its model-evidence read before checking the reader's reconnect latch. If the upstream closes during that read, the existing unsent handoff transfers the turn to a replacement socket without spending the post-send replay budget.

HTTP bridge lookup reads model exclusions for its bounded cached-session snapshot outside the registry lock. Reused and in-flight-created candidates respect that evidence, while a final per-account read catches peer exclusions arriving during admission. A movable request can reselect; conversation and file owners remain fixed. For example, after a peer rejects A/model M, an unanchored request can use B, but a continuation owned by A fails with owner-unavailable.

Late rejection stays outside the send-failure retirement path. It releases the unsent request's admission and API-key reservation while an accepted sibling can still complete. Cancellation of the final lookup follows the same owned cleanup. Unrelated models and expired evidence remain eligible. These database reads add latency; they do not change the pure in-memory global account-availability snapshot or assign global health penalties.

Required-owner checks compare the actual required account with the cached or newly created candidate. For example, a file owned by B remains usable when its prompt-cache key points to excluded A. B is selected, while A's already accepted requests finish before its detached generation closes. The detached registry retains lifecycle and capacity ownership during that drain. A request actually requiring excluded A still fails closed.

Failures during model-evidence lookup return a sanitized HTTP 503 `upstream_unavailable` admission error. This includes raw asyncpg connection/authentication errors, timeouts and SQLAlchemy failures at initial account selection, cache lookup, in-flight reuse, fallback reuse, or final submission. A shared proxy helper limits normalization to this evidence read and lets cancellation propagate. The new request releases its resources without sending, exposing SQL/driver details, penalizing account health, or closing an accepted sibling's transport. Direct WebSocket reuse/final admission emits the corresponding request-local terminal error and keeps the downstream socket available for retry. For example, a failed final lookup while a previous response is streaming leaves that response running; the client can retry the unsent turn once the database is available.

Classified account-neutral goal restarts still reach guarded sticky selection when a cached or in-flight legacy owner is model-excluded. For example, an excluded quota-exceeded legacy owner can be replaced while its already accepted request drains. Model exclusion alone does not permit abandonment of an active legacy owner, and file/previous-response dependencies still pin the request to its required account. Persisted status, scope and atomic sticky ownership remain the authority for replacement.

The direct WebSocket connect selector also handles normalized admission errors before any upstream socket exists. It emits the existing structured connect error and settles the unsent request, letting the receive loop accept another turn on the same downstream socket. The route regression restores the real connector and account selector; a mocked connector alone cannot cover this boundary.

## Code-less usage-limit backport (2026-10-02)

Upstream sometimes omits the code from an exhausted-window error. One normalized predicate now supplies HTTP classification, stream retry/health, usage-refresh triggering and direct WebSocket quota replay classification. It accepts only the existing `usage_limit_reached` code or matching upstream-authored wording on normalized `upstream_error`; explicit request, quota, throttling and transient codes retain their own meaning.

For example, a pre-visible code-less usage-limit frame can move an unpinned request from A to B, while a file-owned turn remains subject to the same owner restrictions. Once text has been emitted, no replay occurs, but the exhausted account still receives its health update after keyed settlement. The client retains the upstream terminal envelope. A proven quota error does not use the code-less-429 burst cooldown, and proxy-authored terminal cleanup keeps code-only classification. Narrow OpenAI-processing-error isolation remains unchanged. See [spec.md](spec.md).

## Subscription model Plan restrictions


The requested targets are native subscription models, not OpenAI-compatible
model sources. An operator restriction therefore belongs in dashboard settings,
independently of upstream `available_in_plans` capability metadata. The default
is `{}`: installation and migration do not seed any model-specific restrictions.
Removing an entry restores that model's existing selection behavior.

The restriction is an intersection, not a preference: exhausted, unavailable,
out-of-scope, or unentitled Free accounts produce the existing routing error
instead of spending paid capacity. Upstream entitlement, health, quota, key
scope, single-account selection, and ranking still apply. Ownership is resolved
before routing eligibility; filtering cannot invent a unique conversation owner
or move file-/conversation-bound work to another account.

### Identity and representation

Keys match exact effective native model IDs after existing alias/API-key handling.
They are case-sensitive and cannot contain whitespace. API configuration does
not require current catalog membership. The UI selects native non-image entries
and retains saved absent IDs for editing/removal; it does not offer source-only
or image-only entries as native choices. A source resolved by existing dispatch
is unaffected even when its slug collides with a configured native slug.

Recognized operator plans are `free`, `plus`, `pro`, `prolite`, `team`, `business`,
`enterprise`, and `edu`. Case and surrounding whitespace are normalized and
lists are deduplicated. Equality is strict: `prolite` does not satisfy `pro`.
Catalog plan labels can be broader than this operator-setting vocabulary;
adding a catalog entitlement does not automatically add a configurable plan.

### Constraints and failure modes

- Omitted or null `modelPlanRoutingPolicies` preserves the mapping; only `{}`
  clears it. Invalid updates fail atomically. Existing authorization, audit,
  version conflicts, and settings propagation apply.
- One non-null JSON-text settings column avoids a second policy source of truth.
  Historical rows receive `{}`. Upgrade is idempotent; downgrade discards this
  mapping, so re-upgrade starts empty while unrelated settings are preserved.
- Policy cache fingerprints distinguish selection pools. Propagation uses the
  existing five-second settings cache and cross-replica invalidation, not
  instantaneous cluster-wide linearizability.
- Warm bridge/WebSocket admission reads current persisted account plans in an
  owned database session outside the bridge registry lock. It rechecks after
  admission waits. Policy rejection is local unsent work: accepted siblings,
  task ownership, reservation settlement, and strict owners remain protected.
- Direct native streaming/compact sends and same-account retries also need the
  effective policy and persisted-plan check after admission waits or backoff.
  A previously eligible selection is not durable permission to send; late
  rejection releases unsent resources without account-health penalties.
- Malformed stored JSON or unavailable policy evidence fails closed with a
  sanitized local admission error, not an upstream health penalty. Restriction
  changes do not terminate already accepted work.
- An invalid stored mapping (manual SQL edit, or a saved plan that is no
  longer recognized) keeps native routing failing closed, but settings stay
  readable: `GET /api/settings` shows only the still-valid entries and logs a
  warning. Every settings save writes the mapping it carries, and an omitted
  field carries that displayed mapping, so a PUT of `{}` or a corrected mapping
  repairs the stored value. For example, stored
  `{"gpt-6-luna": ["free"], "retired-model": ["retired-plan"]}` reads as
  `{"gpt-6-luna": ["free"]}` while native requests return 503 until a save.
- The final direct-send recheck applies only to configured models and reads
  only the persisted account plan. Unconfigured models dispatch as before;
  plan-check rejections recorded by concurrent requests stay selection-time
  evidence that fails over normally.
- Same-account retries after an upstream 5xx or 401 pass the final recheck
  before resending. A confirmed pre-dispatch connect failure instead moves a
  movable stream through fresh selection, which admits only the currently
  effective pool; if that pool is empty, the existing exhausted-retry error
  surfaces. An upstream 401 on an allowed first send keeps its existing health
  penalty; only the admission denial itself is health-neutral.
- Mutation and refetch keep UI controls busy. A conflict refreshes mapping and
  version and resets stale drafts; an ordinary failure leaves a retryable draft.

### Configuration example

After a separately authorized deployment, use `PUT /api/settings` with the
mapping below, including `expectedVersion` from a fresh `GET /api/settings`
when using optimistic concurrency:

```json
{
  "modelPlanRoutingPolicies": {
    "gpt-5.6-terra": ["free"],
    "gpt-5.6-luna": ["free"],
    "gpt-6-luna": ["free"]
  }
}
```

This is an unapplied example, not an installation or migration default. If no
otherwise eligible Free account remains, `gpt-6-luna` fails rather than using a
paid account. A paid file/conversation owner cannot move to Free to satisfy the
restriction. Unconfigured native models and source-dispatched requests retain
their existing behavior; a configured mapping cannot manufacture entitlement.
Removing the model key restores ordinary selection after existing settings
propagation. This documentation does not authorize applying live settings.

## Earlier movement of soft affinity after sustained upstream failure

Three qualified overload/processing failures within 120 seconds already establish sustained backoff. Later independently submitted requests may move a soft prompt-cache/thread/session mapping to an eligible sibling at that first trip; waiting for nine failures before isolation caused unnecessary repeated rejection during the October 12 incident. For example, failures interleaved with successes on A still move the next movable request to B when B passes the strategy, quota and cap checks. A lone owner or an all-unavailable alternative pool retains the existing fallback. Required response/file/bridge/turn-state ownership is unchanged; no accepted request is newly replayed. Burst-only cooldown does not release warm owners.

This reduces repeated admissions to failing accounts; it cannot accelerate upstream generation or repair a provider-wide incident. Signals remain replica-local and writes retain settlement ordering. Isolation still controls the longer hold duration, including its existing disable setting.

## Safety-policy blocks and deactivated workspaces (2026-10-19)

Round 2 (`openspec/changes/backport-upstream-october-reliability-2`) ports two routing fixes:

- **Safety-policy blocks (#2131).** A `misalignment_policy_violation` whose message starts with "This request was blocked by our safety systems." (status none or 400) reproduces on every account. It is forwarded unchanged and never written to account health. The fork keeps its message-aware penalty predicate, including round 1's code-less usage-limit recognition. `cyber_policy` and security-work routing are unchanged. The WebSocket and HTTP-bridge paths were already neutral for this code; route tests now pin it.
- **Deactivated workspaces (#2573).** The exact `deactivated_workspace` code deactivates only the selected routing record. Unbound pre-visible requests fail over, and owner-bound ones surface the rejection.
  - Fork extension: for API-key requests, the deactivation is written only after the reservation is settled, both on the first dispatch and on the redispatch after a forced token refresh. Upstream defers only the first site.
  - Example: a file-pinned keyed request gets 401, refreshes, then gets HTTP 402 `deactivated_workspace`. The client receives the 402, every reservation for the key is closed, then the account becomes `deactivated`, and no sibling is tried.
  - Delivery scope: HTTP 402 and status-less terminal frames. A pre-visible HTTP 500 keeps the generic server-error retry, as on upstream.

## Background account-state builds

The quota planner tick, the quota planner forecast endpoint and the usage-refresh recovery reconciliation resolve soft drain and the routing tunables from one dashboard-settings snapshot, taken outside runtime locks (#2233):
- the planner reads the settings cache once per tick or request;
- recovery reuses the detached row the refresh cycle already read.

Without this, an operator who turned soft drain off in the dashboard still saw these background paths compute the draining tier from the environment default.
