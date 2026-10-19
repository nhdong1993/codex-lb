## MODIFIED Requirements

### Requirement: Pre-visible unary refresh/connect failures fail over

For unary proxy requests that have not emitted downstream-visible output, the proxy MUST treat retryable token-refresh or upstream-connect transport failures as account-local transient failures.

This applies to Codex thread-goal requests, Codex control requests,
transcription requests, and file create/finalize requests. When another
eligible account is available within the request budget, the proxy MUST record
the failed account, exclude it from the current request, and retry the unary
operation on the fallback account. The proxy MUST NOT fail over strict
account-owner requests whose upstream resource is bound to the selected account.

For account-routed file operations, the client and service MUST preserve typed transport phase and replay eligibility. Confirmed pre-dispatch connection failures MUST use the existing account failover policy even when the credential-safe message contains no transient-error phrase. Typed transport errors MUST NOT gain replay eligibility from message text. TLS verification failures, ambiguous request failures, response-body failures, and process-wide network failures MUST NOT cause cross-account file retries. A file-finalize operation MUST NOT fail over to another account after any of its polls has returned an upstream response, even if a later poll fails before dispatch.

#### Scenario: Unary refresh transport failure uses another account

- **GIVEN** at least two accounts are eligible for a Codex thread-goal, Codex
  control, transcription, or file-create request
- **AND** the selected account fails during token refresh or upstream connect
  with a retryable transient transport error before downstream-visible output
- **WHEN** another eligible account can complete the request within the request
  budget
- **THEN** the downstream request succeeds from the fallback account
- **AND** the failed account is recorded and excluded from further attempts for
  that request

#### Scenario: Strict file-owner refresh failure fails closed

- **GIVEN** a file-finalize request is pinned to the account that owns the file
- **AND** the pinned account fails during token refresh or upstream connect with
  a retryable transient transport error before downstream-visible output
- **WHEN** another account would otherwise be eligible for proxy traffic
- **THEN** the proxy fails the request with an upstream-unavailable error
- **AND** the proxy does not send the file-finalize operation through another
  account

#### Scenario: Routed file connection refusal uses another account

- **GIVEN** an unpinned file-create request with another eligible account
- **WHEN** the routed transport proves that the selected account's proxy connection failed before dispatch
- **THEN** the proxy excludes that account and completes the file-create request through the eligible fallback within the existing budget

#### Scenario: Routed file replay is denied without safe provenance

- **GIVEN** a routed file request with another eligible account
- **WHEN** the transport reports a TLS verification failure, ambiguous request failure, response-body failure, or process-wide network failure
- **THEN** the proxy returns the transport error without invoking the file operation through another account
- **AND** transient-looking text in the sanitized message does not permit replay

#### Scenario: First file-finalize poll fails before dispatch

- **GIVEN** an unpinned file-finalize operation with another eligible account and no completed upstream poll
- **WHEN** its first routed poll fails with a confirmed pre-dispatch connection refusal
- **THEN** the proxy MAY complete the operation on the eligible fallback account within the existing budget

#### Scenario: Later file-finalize poll fails before dispatch

- **GIVEN** an unpinned file-finalize operation whose first upstream poll returned `status: retry`
- **WHEN** a later routed poll fails with a confirmed pre-dispatch connection refusal
- **THEN** the proxy MUST return an upstream-unavailable error without invoking any poll through another account

#### Scenario: Pinned file-finalize poll fails

- **GIVEN** a file-finalize operation pinned to its owner account
- **WHEN** its first or a later poll fails before dispatch
- **THEN** the proxy MUST fail closed without invoking a poll through another account

## ADDED Requirements

### Requirement: Observed HTTP response IDs publish same-process ownership before delivery

When an HTTP Responses attempt extracts a valid response ID from an actual upstream lifecycle event, it MUST publish that ID to the existing bounded process owner cache with the selected account and existing API-key/session scope before delivering the event that exposes the ID downstream. An immediate same-process follow-up referencing that ID MUST be able to resolve its known owner without waiting for the originating request-log write or originating stream completion. This readiness MUST apply from the first observed lifecycle event carrying the ID, including `response.created`, `response.queued`, and `response.in_progress`, whether delivered as SSE or adapted from a canonical background JSON acknowledgement; it MUST NOT promise that an unfinished response is already usable by the upstream provider.

The service MUST NOT publish a locally generated request/synthetic-error ID or a client-supplied anchor as new upstream ownership evidence. Cache misses MUST retain the existing durable request-log lookup and genuinely unknown-owner fail-closed behavior. Request-log persistence MUST remain under its existing detached task owner; this requirement MUST NOT introduce synchronous log barriers, a new registry or a cross-replica readiness guarantee.

When the stream is eligible for capacity replay, lifecycle frames held by the capacity-replay prelude MUST be published when the hold releases, which is when they are delivered. An attempt that the capacity replay discards MUST NOT publish its response ID, including the ID carried by its output-free capacity terminal; the replacement attempt's delivered ID is published as usual.

Provenance for locally generated terminals MUST remain internal to the SSE carrier, preserve the exact serialized event bytes and existing retry markers, and survive reattachment of the parsed payload.

When normalization of an actual upstream error supplies a local response ID, that ID MUST remain ineligible for early ownership publication. The event MUST retain its upstream origin for timing observations.

#### Scenario: Follow-up starts after response-created delivery
- **GIVEN** two eligible accounts and an HTTP stream that has exposed its upstream response ID in `response.created` but has not completed
- **WHEN** a same-process HTTP follow-up references that ID
- **THEN** the known selected account is resolved before upstream dispatch
- **AND** ownership resolution does not wait for the first stream's terminal event or request-log write

#### Scenario: Terminal follow-up races detached persistence
- **GIVEN** a successful HTTP response whose request-log persistence is still pending
- **WHEN** the client submits an anchored follow-up immediately after terminal delivery or EOF
- **THEN** the existing process cache resolves the response owner in the existing caller scope
- **AND** the request is not rejected as unknown-owner solely because that write is pending

#### Scenario: Unobserved and out-of-scope IDs do not gain ownership
- **WHEN** a request references an ID not authoritatively observed for its allowed owner scope, including a local synthetic ID
- **THEN** no new cache entry is inferred from that request
- **AND** existing durable lookup, authorization and unknown-owner fail-closed rules apply

#### Scenario: Background acknowledgement precedes its log
- **GIVEN** two eligible accounts and a canonical HTTP background JSON acknowledgement with status `queued` or `in_progress`
- **WHEN** the same caller submits a continuation after receiving the acknowledgement while its log is pending
- **THEN** the known owner MUST resolve and receive that continuation without waiting for the originating log
- **AND** the acknowledgement MUST preserve its upstream ID and status

#### Scenario: In-progress lifecycle follows token delivery
- **GIVEN** an HTTP stream has delivered a text delta and first exposes its authoritative response ID in `response.in_progress`
- **WHEN** the event reaches the caller before stream completion
- **THEN** a same-process continuation MUST resolve the known owner before upstream dispatch

#### Scenario: A capacity-replayed attempt publishes no owner
- **GIVEN** an eligible stream whose first account sends `response.created` and then an output-free capacity terminal with the same response ID
- **AND** a second account delivers a different response ID
- **WHEN** the proxy replays the request on the second account
- **THEN** the discarded response ID is not published to the owner cache
- **AND** the delivered response ID resolves to the second account

### Requirement: HTTP bridge model-transition owner conflicts fork a guarded child lane

When a hard continuity lookup identifies a durable owner for an incompatible model and HTTP bridge creation returns `continuity_owner_conflict`, the service MUST retry at most once on a new account-neutral child lane when the request is local, has no `previous_response_id`, has no resolved file owner, and the effective payload passes the account-neutral fresh-replay validator. The child lane MUST exclude the conflicting owner, force local creation, use hard affinity, and clear parent-derived affinity, hard-continuity, and reused turn-state identity before submitting the request.

#### Scenario: Eligible model transition conflict forks once

- **GIVEN** a durable hard continuity key belongs to account A for the old model
- **AND** the new request uses an incompatible model with account-neutral input
- **WHEN** HTTP bridge creation returns `continuity_owner_conflict`
- **THEN** the service retries once on a new hard account-neutral lane
- **AND** the retry excludes account A and does not forward the request

#### Scenario: Child lane does not inherit parent identity

- **GIVEN** the model-transition request reuses the parent turn-state header
- **WHEN** the service forks to the account-neutral child lane
- **THEN** the submitted child request has no parent session id
- **AND** it has no parent affinity policy or hard-continuity anchor

#### Scenario: Second conflict remains fail-closed

- **GIVEN** the service already forked once for the model-transition request
- **WHEN** the child lane also returns `continuity_owner_conflict`
- **THEN** the service returns that error without creating another child lane
