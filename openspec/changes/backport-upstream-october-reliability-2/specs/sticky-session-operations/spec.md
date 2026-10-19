## ADDED Requirements

### Requirement: Request-local unavailability of a soft TTL-bounded owner is non-mutating

When a soft TTL-bounded (`prompt_cache`) mapping resolves to an owner that is absent from the request's selectable candidates only because of request-local pressure, selection MUST serve the request from an alternate eligible account without deleting or rebinding the mapping, and MUST emit the internal `internal_soft_affinity_spillover` diagnostic; when the request asks for sensitive-detail redaction, that diagnostic MUST NOT include the owner or alternate account identifiers. Request-local pressure is exactly: (a) the owner is in the request's routable pool but filtered by the per-account concurrency caps, or (b) the owner is in the request's excluded set (this request's retry loop already failed over from it after a transient upstream failure) while it remains in the request's continuity-owner scope with a persisted status of `active`, `reauth_required`, `rate_limited` or `quota_exceeded`. The alternate MUST apply only to that request; a later request on the same mapping MUST return to the owner once it is selectable. An owner removed from the candidates only by model or plan admission rejection is not request-local pressure. Selection MUST still rebind the mapping to the fallback, as before, when the owner is in sustained-overload backoff (including its first trip below the isolation stage, per "Isolated accounts release their soft sticky owners"), when the owner was removed by model or plan admission rejection, when the request explicitly reallocates the mapping, when the owner's persisted status is `paused` or `deactivated`, or when the owner is outside the request's continuity-owner scope (removed, out of API-key scope, or not authorized for a security-work request). Hard mappings and durable `codex_session` mappings without a TTL keep their existing rules.

#### Scenario: Capped prompt-cache owner spills without rebinding

- **GIVEN** a `prompt_cache` thread mapping points to account A
- **AND** account A is at its per-account stream cap
- **AND** account B is eligible and below cap
- **WHEN** a request on that thread selects an account with a stream lease
- **THEN** account B is selected for this request
- **AND** the mapping still points to account A and no sticky row is written or deleted
- **AND** `internal_soft_affinity_spillover` is emitted
- **AND** once account A's cap clears the next request on that thread selects account A

#### Scenario: Owner excluded after a transient upstream failure spills without rebinding

- **GIVEN** a `prompt_cache` thread mapping points to account A whose persisted status is `active`
- **AND** the request's retry loop excluded account A after a transient upstream failure on this turn
- **AND** account B is eligible
- **WHEN** the retry re-selects an account with account A excluded
- **THEN** account B is selected for this request
- **AND** the mapping still points to account A and no sticky row is written or deleted
- **AND** the next turn on that thread, with no exclusion, selects account A

#### Scenario: Spillover diagnostic honours request redaction

- **GIVEN** a `prompt_cache` thread mapping points to account A and the request has excluded account A after a transient failure
- **AND** the request asks for sensitive-detail redaction
- **WHEN** the request selects an account and spills to account B
- **THEN** `internal_soft_affinity_spillover` is emitted with both account identifiers redacted

#### Scenario: Backed-off capped owner is still rebound

- **GIVEN** a `prompt_cache` thread mapping points to account A, which is at its stream cap and in sustained-overload backoff
- **AND** account B is eligible and not in overload backoff
- **WHEN** a request on that thread selects an account
- **THEN** account B is selected and the mapping is rebound to account B

#### Scenario: Explicit reallocation still rebinds a capped owner

- **GIVEN** a `prompt_cache` thread mapping points to account A, which is at its stream cap
- **WHEN** a request on that thread selects an account with sticky reallocation requested
- **THEN** the mapping is rebound to the selected alternate

#### Scenario: Excluded owner outside the continuity scope is rebound

- **GIVEN** a `prompt_cache` thread mapping points to account A, which is not authorized for security work
- **AND** the request requires security-work authorization and has excluded account A
- **WHEN** the request selects an account
- **THEN** the authorized alternate is selected and the mapping is rebound to it

#### Scenario: Excluded paused owner is rebound

- **GIVEN** a `prompt_cache` thread mapping points to account A whose persisted status is `paused`
- **AND** the request has excluded account A
- **WHEN** the request selects an account
- **THEN** the alternate is selected and the mapping is rebound to it

#### Scenario: Bare process-session owner without a TTL keeps persisting its fallback

- **GIVEN** a bare `codex_session` mapping without a TTL points to account A
- **AND** the request has excluded account A
- **WHEN** the request selects an account
- **THEN** the alternate is selected and the mapping is rebound to it, as today

#### Scenario: Owner rejected by plan or model admission is rebound

- **GIVEN** a `prompt_cache` thread mapping points to account A
- **AND** model or plan admission rejects account A for the requested model
- **WHEN** the request selects an account
- **THEN** an admitted alternate is selected and the mapping is rebound to it

### Requirement: A hard-affinity saturation caused by the caller's own exclusion is not waited on

When account selection fails with `hard_affinity_saturated`, the selector MUST
report whether the resolved hard `CODEX_SESSION` owner is one of the account
ids the caller asked to exclude from that selection. The report MUST be true
only for that combination: a saturation whose owner the caller did not exclude,
and any other selection outcome, MUST NOT be reported as caller-excluded.

A hard row is ownership evidence, so selection narrows to its owner and never
spills to another account, and the exclusion filter removes the owner from the
candidate pool before that narrowing. A caller that excluded the owner
therefore cannot be served by any re-selection while its exclusion holds. When
the selector reports that cause, the caller MUST NOT take the short
owner-recovery wait that a briefly unavailable owner earns, and MUST fail the
request closed on that first saturated selection instead of re-selecting until
its request budget is spent. The failure's error code, HTTP status and payload
MUST be unchanged from the same failure surfaced after the wait.

The rule MUST hold for every transport that waits on selection recovery — the
HTTP responses session bridge (session creation and reconnect), the direct
WebSocket surface, and the SSE retry path — so no surface keeps spinning after
another stops. It MUST NOT change any selection decision: the exclusion stands,
the sticky row is neither rebound nor deleted, no alternate account is served
for a resolved hard owner, and an owner the caller did not exclude keeps both
its recovery wait and its retry.

#### Scenario: Raw legacy hard owner excluded by the requesting replay

- **GIVEN** a native Codex session whose bare session header still resolves a raw legacy `CODEX_SESSION` row naming account A as the hard owner, and no namespaced row
- **AND** a healthy alternate account B is selectable
- **WHEN** selection runs with that affinity and `exclude_account_ids` containing A
- **THEN** selection fails with `hard_affinity_saturated` and never returns B
- **AND** the failure reports that the resolved hard owner is one of the caller's own exclusions
- **AND** the sticky row still names A, unrewritten and undeleted

#### Scenario: Bridge replay that excluded its own hard owner fails closed at once

- **GIVEN** the HTTP responses session bridge is enabled and a native Codex request carries a `session_id` header whose raw legacy row names the serving account as the hard owner
- **AND** the turn fails before `response.created` reaches the client (the created-only pre-created replay) or the account rejects the requested model (the model-fallback replay), so the replay excludes that account to move the turn
- **WHEN** the reconnect re-selects and selection reports the caller-excluded hard owner
- **THEN** the reconnect fails the request closed on that first re-selection without waiting for the owner to recover
- **AND** the turn is not sent to another account, and the owner is not reconnected behind the client's back
- **AND** the client observes the resulting failure immediately instead of keepalives until the bridge request budget

#### Scenario: Unavailable owner the caller did not exclude keeps its recovery wait

- **GIVEN** the same session whose raw legacy row names account A as the hard owner
- **AND** A is temporarily unselectable through a status or health transition while the caller excludes nothing
- **WHEN** selection fails with `hard_affinity_saturated`
- **THEN** the failure is not reported as caller-excluded
- **AND** the caller takes its short owner-recovery wait and re-selects, so the owner may serve the turn once it recovers

### Requirement: Pre-dispatch owner recovery reuses the original reservation

The origin MUST reuse the original API-key reservation during pre-dispatch local recovery.
This applies when an owner-forwarded bootstrap request is rejected before upstream
dispatch and the origin enters its existing recovery path. It MUST NOT acquire
a second reservation for the same request.

The reservation lifecycle MUST still settle exactly once. A cancellation,
acknowledged owner response, or ambiguous dispatch failure MUST remain on its
existing fail-closed path and MUST NOT be treated as a local pre-dispatch
recovery.

#### Scenario: Local recovery transfers the original hold

- **GIVEN** an API-key request owns a reservation
- **AND** the HTTP bridge owner rejects the bootstrap request before dispatch
- **WHEN** the origin creates the local recovery request
- **THEN** the local request carries the original reservation identity
- **AND** no second reservation is acquired

#### Scenario: Ambiguous dispatch remains fail-closed

- **GIVEN** an API-key request owns a reservation
- **AND** owner forwarding is acknowledged or dispatch status is ambiguous
- **WHEN** forwarding fails
- **THEN** the origin does not enter local pre-dispatch recovery
