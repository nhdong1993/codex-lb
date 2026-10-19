## MODIFIED Requirements

### Requirement: Rate-limit cooldowns are enforced across replicas

A replica that did not observe the upstream 429 MUST NOT transition a `RATE_LIMITED` account to `ACTIVE` while the persisted `reset_at` deadline is in the future unless background usage refresh proves that the exact blocked quota window reset under the strict exception below. For `RATE_LIMITED` rows with `blocked_at` set but no persisted `reset_at` (legacy rows written before cooldown persistence), replicas MUST hold the account `RATE_LIMITED` until at least `blocked_at + RATE_LIMITED_MIN_COOLDOWN_SECONDS`. Recovery transitions MUST be written through the compare-and-set status update (`update_status_if_current`) so a stale snapshot cannot clobber a newer marking.

The reset-confirmed exception SHALL apply to any account with a still-future persisted deadline after the 30-second minimum floor has elapsed, and SHALL be bound to a window rather than to the account's plan. Post-block history in exactly one quota-window slot MUST contain a baseline whose reset deadline matches the persisted account deadline within five seconds, and a deadline matching the baseline of more than one slot MUST disqualify the exception because it does not identify the blocked window, whether or not those slots went on to reset, and an adjacent before/after pair from that same slot at or after that baseline MUST prove a real temporal reset. Both the after sample and the latest sample of that slot MUST be post-block and below `100%`. When the anchored window is not the short window, recovery MUST additionally be withheld while the account's short (`primary`) window reports `100%` and has not itself elapsed, unless that slot's quota capacity for the plan is known to be zero or its row reports a recognized long window's duration; an unrecognized duration MUST count as the short window. This is the only cross-window condition; a long window at `100%` MUST NOT withhold recovery, because credit-backed quota and weekly-shape normalization govern whether it still permits traffic. The recovery compare-and-set MUST match the persisted status, deactivation reason, `reset_at`, and `blocked_at`, then clear both markers when it writes `ACTIVE`. The evidence MAY be loaded from persisted history after a process restart, but availability alone and comparisons between non-neighboring rows MUST NOT satisfy the exception.

This constraint applies to every recovery path that writes account status, including the usage-refresh reconcile path. A usage refresh that observes available quota for a `RATE_LIMITED` account with `blocked_at` set MUST NOT rewrite the account to `ACTIVE` or clear its markers while the effective persisted cooldown is running unless the strict reset-confirmed exception succeeds. The replica that observed the current 429 MAY still recover earlier through its runtime-cooldown-gated fresh-usage path only when its runtime block marker is at least as recent as the effective persisted `blocked_at`; leftover runtime state from an earlier 429 MUST NOT unlock early recovery of a newer block. `RATE_LIMITED` rows without `blocked_at` keep the existing fresh-usage recovery. Generic 429 and Retry-After cooldowns without matching reset evidence, reset timestamp jitter, exhausted post-reset windows, and an exhausted unelapsed short window MUST remain protected until their ordinary recovery condition is met.

#### Scenario: Usage refresh does not clear a running Retry-After cooldown

- **GIVEN** an account marked `RATE_LIMITED` by a 429 whose Retry-After hint persisted `reset_at` 20 minutes in the future and `blocked_at` set
- **WHEN** a periodic usage refresh fetches fresh usage showing available quota before that deadline
- **AND** no qualifying reset transition matches the persisted deadline
- **THEN** the persisted row keeps status `RATE_LIMITED` with its `reset_at` and `blocked_at` intact
- **AND** once the deadline elapses, a later refresh may recover the account to `ACTIVE` through the compare-and-set path

#### Scenario: Confirmed blocked Free monthly reset permits peer recovery

- **GIVEN** replica A marked a Free account `RATE_LIMITED` with `blocked_at` and a persisted deadline matching that account's monthly window
- **AND** the 30-second minimum floor has elapsed
- **WHEN** replica B observes a real post-block transition from the matching monthly baseline into a new available monthly window
- **AND** the latest monthly sample remains below `100%`
- **THEN** replica B may compare-and-set the account to `ACTIVE` before the old persisted deadline
- **AND** a successful transition clears `reset_at` and `blocked_at`

#### Scenario: Confirmed blocked window reset permits peer recovery on any plan

- **GIVEN** replica A marked an account `RATE_LIMITED` with `blocked_at` and a persisted deadline matching one of that account's quota windows
- **AND** the 30-second minimum floor has elapsed
- **WHEN** replica B observes a real post-block transition from the matching baseline into a new available window in that same slot
- **AND** the latest sample of that slot remains below `100%`
- **AND** the account's short window is not itself exhausted and unelapsed
- **THEN** replica B may compare-and-set the account to `ACTIVE` before the old persisted deadline
- **AND** a successful transition clears `reset_at` and `blocked_at`

#### Scenario: Paid account recovers after an early upstream weekly reset

- **GIVEN** a Pro account is `RATE_LIMITED` on its exhausted 7d window with a persisted deadline days in the future
- **AND** the 30-second minimum floor has elapsed
- **AND** upstream re-anchors that 7d window early and reports it at `0%`
- **WHEN** background usage refresh records the post-block transition in that window's slot
- **AND** the account's short window is not itself exhausted and unelapsed
- **THEN** the account may be recovered to `ACTIVE` before the persisted deadline
- **AND** the recovery clears `reset_at` and `blocked_at`

#### Scenario: Generic 429 without matching reset evidence remains protected

- **GIVEN** an account has a future persisted cooldown from an upstream 429 or Retry-After hint
- **AND** fresh usage reports availability but no temporal reset whose baseline matches that deadline
- **WHEN** any replica evaluates recovery
- **THEN** the account remains `RATE_LIMITED` until an ordinary recovery condition is met

#### Scenario: Peer replica does not flip a cooling account back

- **GIVEN** balancer instance A marked account X `RATE_LIMITED` from a 429 with no reset metadata
- **AND** account X's recorded usage is below 100%
- **WHEN** a second balancer instance sharing the same database runs account selection
- **THEN** account X is not selected
- **AND** the persisted row remains `RATE_LIMITED` with its `reset_at` deadline intact until the deadline elapses or strict reset-confirmed recovery succeeds

#### Scenario: Stale runtime cooldown does not unlock early recovery of a newer block

- **GIVEN** a replica holds expired runtime cooldown state left over from an earlier 429 of account X
- **AND** account X was since re-marked `RATE_LIMITED` by a peer replica with a newer `blocked_at` and a future persisted `reset_at`
- **WHEN** the replica evaluates account X with usage recorded after the newer `blocked_at`
- **AND** no strict reset-confirmed transition matches the newer block
- **THEN** account X stays `RATE_LIMITED` and is not selected until the persisted deadline elapses

#### Scenario: Concurrent newer block wins the recovery race

- **GIVEN** reset evidence qualifies a blocked account for early recovery
- **AND** another replica changes its status or either block marker before recovery commits
- **WHEN** the recovery compare-and-set evaluates the older snapshot
- **THEN** it does not overwrite the newer account row
- **AND** the account is not made routable from the stale evidence

#### Scenario: Exhausted Plus primary window remains protected

- **GIVEN** a Plus account is `RATE_LIMITED` with primary usage at `100%` and an unelapsed primary reset deadline
- **WHEN** a replica observes available long-window usage or a long-window reset
- **THEN** the reset-confirmed exception does not apply, because the primary window carries quota for the plan and is still exhausted
- **AND** the account remains unavailable until its ordinary recovery condition is met

#### Scenario: Legacy row without reset_at is floored

- **GIVEN** a persisted `RATE_LIMITED` row with `blocked_at` five seconds ago and `reset_at` NULL
- **WHEN** a fresh balancer instance evaluates it during selection
- **THEN** the account stays `RATE_LIMITED` and is not selected
- **AND** once the 30-second floor has elapsed, recovery back to `ACTIVE` is permitted through the compare-and-set path

### Requirement: Upstream rejections of the request payload are account neutral

When upstream rejects a request because of the request payload itself, the
proxy MUST NOT mutate the selected account's health: it MUST NOT record a
transient account error, a rate-limit penalty, a quota penalty, or a permanent
failure for that account. An upstream failure qualifies as a payload rejection
only when it would reproduce identically on every account. The proxy MUST
decide membership from the classified upstream message, never from the
`invalid_request_error` code alone, and MUST require the upstream HTTP status
to be 400 whenever a status is known. An upstream missing-tool-output
rejection — the `invalid_request_error` whose message identifies a tool call
with no matching tool output — MUST qualify. An upstream safety-policy
rejection with code `misalignment_policy_violation`, HTTP status 400 when a
status is known, and a message beginning `This request was blocked by our
safety systems.` MUST also qualify. A different code, a known non-400 status,
or an unrelated message MUST keep its existing account-health handling. The
proxy MUST also leave account health untouched for the model-entitlement
rejection `The '<model>' model is not supported when using Codex with a
ChatGPT account.`: that rejection is scoped to the named model and is not
evidence about the account's ability to serve the models it is entitled to.
Because upstream delivers that rejection on the streaming path with neither
an error `code` nor an error `type`, which normalizes to the `upstream_error`
fallback, the proxy MUST decide it from the message and the 400 status alone
and MUST NOT require a particular normalized error code. Skipping the penalty
MUST be logged so the decision is observable, and MUST NOT change the failure
classification, the failover decision, or the status and body returned to the
client.

#### Scenario: Missing-tool-output rejection leaves account health untouched

- **GIVEN** account A is selected for a request whose input references a tool call with no matching tool output
- **WHEN** upstream returns HTTP 400 `invalid_request_error` with a missing-tool-output message
- **THEN** the proxy does not increment account A's transient error count and does not mark it rate-limited, quota-exceeded, or permanently failed
- **AND** the failure is still classified `non_retryable` and surfaced to the client unchanged

#### Scenario: Repeated client payload rejection cannot starve unrelated sessions

- **GIVEN** one client repeatedly re-sends the same payload that upstream rejects for a missing tool output
- **WHEN** those requests are served by accounts shared with other sessions
- **THEN** no serving account enters error backoff because of that payload
- **AND** a session hard-pinned to one of those accounts is not failed with a saturated-hard-affinity selection error caused by that payload

#### Scenario: Model-entitlement rejection leaves account health untouched

- **GIVEN** account A is selected for a model it is not entitled to use
- **WHEN** upstream returns HTTP 400 stating the model is not supported when using Codex with a ChatGPT account, with the error code normalized to `upstream_error` or to `invalid_request_error`
- **THEN** the proxy does not increment account A's transient error count and does not mark it rate-limited, quota-exceeded, or permanently failed
- **AND** the skip is logged

#### Scenario: Model-entitlement rejection still fails over

- **GIVEN** account A returned the model-entitlement rejection for the requested model
- **WHEN** the proxy classifies that failure
- **THEN** the classification and failover decision are unchanged, so an account with a different entitlement is still attempted
- **AND** the status and body returned to the client when every attempt is exhausted are unchanged

#### Scenario: A model no source can serve cannot poison subscription accounts

- **GIVEN** a model that resolves to no enabled model source and therefore reaches subscription account selection
- **WHEN** a client polls that model repeatedly and every subscription account returns the model-entitlement rejection
- **THEN** no serving account enters error backoff because of those rejections
- **AND** unrelated traffic hard-pinned to those accounts is not denied with a continuity-owner-unavailable or no-available-accounts selection error caused by them

#### Scenario: Model-entitlement rejection still penalizes the account

- **GIVEN** account A is selected for a request
- **WHEN** upstream fails with a non-400 status whose message matches the model-entitlement rejection
- **THEN** the proxy records the account-health penalty for account A as before, because only a genuine HTTP 400 qualifies as the model-scoped rejection

#### Scenario: A genuine upstream failure still penalizes the account

- **GIVEN** account A is selected for a request
- **WHEN** upstream fails with an `upstream_error` whose message is not the model-entitlement rejection
- **THEN** the proxy records the account-health penalty for account A as before

#### Scenario: Safety-policy rejection leaves account health untouched

- **GIVEN** account A is selected for a request
- **WHEN** upstream returns `misalignment_policy_violation` with HTTP status
  400 or no separately available status and the safety-system block message
- **THEN** the proxy does not increment account A's transient error count and
  does not mark it rate-limited, quota-exceeded, or permanently failed
- **AND** the failure remains classified as non-retryable

#### Scenario: Similar non-policy failure keeps its health handling

- **WHEN** an upstream failure has a different code, a known non-400 status,
  or a message that does not identify the safety-system block
- **THEN** the proxy does not classify it as an account-neutral safety-policy
  rejection
- **AND** its existing account-health handling remains in effect

## ADDED Requirements

### Requirement: Explicit workspace deactivation excludes only the selected routing record

The proxy MUST treat the exact upstream error code `deactivated_workspace` as a terminal unavailable-workspace signal for the selected account routing record. It MUST use the existing permanent-failure status policy to persist `deactivated`, record a workspace-specific reason, and exclude that record from future account selection. It MUST NOT deactivate other account or workspace records solely because they share an identity.

#### Scenario: An unavailable workspace is removed from future selection

- **GIVEN** workspace record A and healthy workspace record B are eligible
- **WHEN** an upstream request through A is rejected with `deactivated_workspace`
- **THEN** A is marked `deactivated` with reason `Workspace has been deactivated`
- **AND** B remains eligible and unchanged
- **AND** subsequent selection does not select A


### Requirement: Movable pre-visible workspace rejections may fail over

When deterministic failover is enabled, the proxy MUST classify `deactivated_workspace` as `account_unavailable` and MAY try the next eligible candidate within the existing attempt budget only before downstream-visible output and only when the request is not bound to an account owner. It MUST NOT retry the rejected workspace or move file-, reasoning-, turn-state-, previous-response-, or single-account-owned payloads to another account. Existing API-key reservation settlement MUST complete before the deferred `deactivated` health write, both when the rejection arrives on the first dispatch and when it arrives on the redispatch after a forced token refresh.

#### Scenario: An account-neutral Responses request uses a healthy alternative

- **GIVEN** an account-neutral request with no downstream-visible output
- **AND** a healthy alternative candidate remains
- **WHEN** the selected workspace returns HTTP 402 with `deactivated_workspace`
- **THEN** the proxy excludes the rejected record and tries the healthy alternative
- **AND** the caller receives the alternative's completed response rather than the first rejection

#### Scenario: An owner-bound rejection fails closed

- **GIVEN** a request is bound to a file, reasoning, turn-state, previous-response, or single-account owner
- **WHEN** that owner's workspace returns `deactivated_workspace`
- **THEN** the request does not cross accounts or retry the unavailable owner
- **AND** the upstream failure is surfaced through the existing error contract

#### Scenario: Visible output prevents replay

- **GIVEN** downstream-visible output has already been emitted
- **WHEN** the workspace becomes unavailable
- **THEN** no alternative account receives a replay of the request

#### Scenario: A keyed rejection after a token refresh settles before deactivation

- **GIVEN** an API-key request whose first dispatch is rejected with HTTP 401 and whose token refresh succeeds
- **AND** the request is owner-bound, or the refreshed dispatch is its last attempt
- **WHEN** the refreshed dispatch is rejected with `deactivated_workspace`
- **THEN** every reservation for the key is finalized, settled or released before the account is marked `deactivated`
- **AND** no sibling account is dispatched for an owner-bound request
- **AND** the caller receives the upstream rejection through the existing error contract
