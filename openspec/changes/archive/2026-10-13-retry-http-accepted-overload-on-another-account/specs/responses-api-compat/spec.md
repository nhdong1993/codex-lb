## ADDED Requirements

### Requirement: Direct HTTP/SSE output-free capacity terminals are replayed once on another account

A direct HTTP/SSE Responses stream is a downstream HTTP request whose upstream transport is HTTP, not the HTTP responses bridge. Such a stream is movable when all of the following hold:

- the request carries no `previous_response_id`
- it references no account-scoped uploaded file
- it resolves to no turn-state or other hard continuity owner
- it is not required to stay on a preferred account
- the routing strategy is not `single_account`
- deterministic failover is enabled
- at least one further account attempt and part of the request budget remain

For a movable stream, the proxy MUST hold the upstream lifecycle prelude downstream. The prelude is `response.created`, `response.in_progress`, `response.queued`, and any non-`response.*` frame received before the first other upstream event. The hold ends at the first upstream event that is neither a prelude frame nor a terminal `response.failed` / `error`. The proxy MUST then forward the held frames in their original order, followed by that event, and the rest of the stream MUST be forwarded exactly as without the hold. The existing SSE heartbeat behavior MUST continue while frames are held.

An output-free capacity terminal is a `response.failed` or `error` event that meets all of the following:

- it arrives while only prelude frames have been received, or as the first upstream event
- its normalized code is `server_is_overloaded`, `overloaded_error`, or `model_at_capacity`, or its message names the selected-model capacity
- its code is not a quota or rate-limit code (`rate_limit_exceeded`, `usage_limit_reached`, `insufficient_quota`, `usage_not_included`, `quota_exceeded`)
- it reports no output: no non-empty `output` list and no positive `output_tokens` or `output_tokens_details.reasoning_tokens`, on the event or under its `response`

When a movable stream receives an output-free capacity terminal, the proxy MUST:

- discard the held frames and the terminal
- record the capacity failure against the account, so overload backoff observes it; for an API-key-backed request this health write MUST wait for the request's reservation settlement
- exclude that account
- send the request once on another account

The client MUST observe only the replacement attempt's events, with exactly one `response.created`.

A request MUST receive at most one such capacity replay. The proxy MUST end the request with a terminal failure carrying the upstream capacity error code and message, and MUST NOT report `no_accounts`, when any of the following occurs:

- the replacement attempt also fails with an output-free capacity terminal
- no other account is selectable
- the request budget is exhausted

Public `/v1/responses` streams MUST still begin with `response.created`.

Each upstream attempt MUST remain recorded in request logs. The replayed attempt keeps its capacity error code and the account it ran on.

A stream that is not movable MUST NOT hold the prelude and MUST surface a capacity terminal unchanged, exactly as before this requirement.

#### Scenario: Accepted overload on a movable stream is replayed on another account

- **GIVEN** two selectable accounts A and B and a movable direct HTTP/SSE stream routed to A
- **AND** A's upstream emits `response.created`, `response.in_progress`, then `response.failed` with `code = "server_is_overloaded"` and no output
- **WHEN** the proxy processes that terminal
- **THEN** the request is sent once to B
- **AND** the client receives exactly one `response.created` (B's) and B's `response.completed`
- **AND** A receives a capacity health failure and is excluded from the replacement selection
- **AND** request logs contain A's attempt with `server_is_overloaded` and B's successful attempt

#### Scenario: A first-event capacity terminal on a movable stream is replayed

- **GIVEN** two selectable accounts and a movable direct HTTP/SSE stream
- **WHEN** the first upstream event is `response.failed` or `error` with `code = "server_is_overloaded"`, `overloaded_error`, `model_at_capacity`, or the selected-model capacity message, and no output
- **THEN** the proxy sends the request once to the other account instead of surfacing the terminal

#### Scenario: A second capacity failure surfaces one terminal without a third send

- **WHEN** the replacement attempt also ends with an output-free capacity terminal
- **THEN** the proxy MUST NOT send the request a third time
- **AND** the client receives one terminal failure carrying the capacity error code

#### Scenario: No alternate account surfaces the capacity error, not no_accounts

- **GIVEN** a movable direct HTTP/SSE stream whose only selectable account returns an output-free capacity terminal
- **WHEN** no other account can be selected for the replay
- **THEN** the client receives a terminal failure carrying that capacity error code and message
- **AND** the client does not receive a `no_accounts` error

#### Scenario: Model output before the capacity terminal disables the replay

- **WHEN** a movable stream receives `response.output_item.added`, a text, reasoning, or tool delta, or any other non-prelude `response.*` event before a capacity terminal
- **THEN** the held prelude is forwarded before that event
- **AND** a later capacity terminal is forwarded unchanged without a replay

#### Scenario: A terminal reporting output is not replayed

- **WHEN** a capacity terminal carries a non-empty `output` list, `usage.output_tokens > 0`, or `usage.output_tokens_details.reasoning_tokens > 0`
- **THEN** the proxy forwards the held prelude and the terminal unchanged without a replay

#### Scenario: Non-capacity terminals keep fail-closed handling

- **WHEN** a movable stream's terminal carries `server_error`, a quota or rate-limit code (even with the selected-model capacity message), or any other non-capacity code
- **THEN** the proxy forwards the held prelude and the terminal unchanged without a replay

#### Scenario: An upstream body that ends during the hold is not replayed

- **WHEN** the upstream body closes, times out, or errors while only prelude frames are held
- **THEN** the proxy forwards the held prelude and applies the existing incomplete-stream handling without a replay

#### Scenario: Streams that cannot move keep the existing contract

- **WHEN** a direct HTTP/SSE stream carries `previous_response_id`, an account-scoped file reference, a turn-state or hard continuity owner, or a required preferred account, or the routing strategy is `single_account`
- **THEN** the proxy forwards `response.created` without holding it
- **AND** an output-free capacity terminal is surfaced unchanged without a replay

#### Scenario: Successful turns are forwarded unchanged

- **WHEN** a movable stream's upstream emits `response.created`, `response.in_progress`, output events, and `response.completed`
- **THEN** the client receives the same events in the same order with the same payloads

## MODIFIED Requirements

### Requirement: Model-capacity messages are retryable transient failures

When upstream returns a temporary model-capacity failure whose message says that the selected model is at capacity, the proxy MUST treat the failure as retryable transient even if the upstream error code or HTTP status would otherwise look non-retryable.

#### Scenario: Selected model capacity with invalid request code is retryable

- **WHEN** upstream returns an error envelope with `error.message = "Selected model is at capacity. Please try a different model."`
- **AND** the normalized error code is `invalid_request_error`
- **AND** the HTTP status is `400`
- **THEN** `classify_upstream_failure` returns `failure_class = "retryable_transient"`
- **AND** pre-visible streaming/websocket paths are eligible to retry or fail over instead of surfacing a terminal client error.

#### Scenario: Serialized selected-model capacity event surfaces without replay

- **WHEN** a streaming Responses request receives a first upstream `response.failed` or `error` event whose message says the selected model is at capacity
- **AND** no downstream-visible output has been emitted
- **AND** the request is not a movable direct HTTP/SSE stream, or the terminal does not meet the output-free proof (it reports output or carries a quota or rate-limit code), or the request already used its capacity replay
- **THEN** the proxy MUST surface that terminal event without transparently re-POSTing the request
- **AND** the absence of an upstream response id MUST NOT by itself prove the POST was safe to replay; only the output-free capacity proof defined by "Direct HTTP/SSE output-free capacity terminals are replayed once on another account" authorizes a re-POST.

#### Scenario: Post-connect body-read disconnect is not replayed as capacity retry

- **WHEN** a streaming Responses request fails while reading the upstream stream body after the upstream request has been dispatched
- **AND** the failure is an `aiohttp` client error, timeout, EOF, or other transport/body-read close without typed pre-dispatch provenance
- **THEN** the proxy MUST surface the stream failure to the downstream client
- **AND** the proxy MUST NOT transparently re-POST the request as a model-capacity retry.

#### Scenario: Websocket connect failure retries before request dispatch

- **WHEN** an upstream websocket handshake raises a typed connector failure or connect timeout before the `response.create` frame is sent
- **THEN** the proxy MUST preserve typed pre-dispatch provenance and MAY retry or fail over before any downstream-visible output
- **AND** a websocket transport selection MUST NOT turn that failure into a terminal serialized SSE event.

#### Scenario: Direct HTTP TLS verification failure is not retried

- **WHEN** a direct HTTP stream raises a certificate or TLS connector failure before request dispatch
- **THEN** the proxy MUST surface the TLS failure without transparently retrying or failing over
- **AND** pre-dispatch provenance MUST NOT classify the non-transient TLS failure as retryable.

#### Scenario: Quota and rate-limit codes retain their stronger classification

- **WHEN** upstream returns a quota or rate-limit error code
- **THEN** the proxy MUST keep classifying it as quota or rate-limit before applying message-based model-capacity detection.

#### Scenario: Post-refresh transient exhaustion preserves every health signal

- **WHEN** one or more accounts each exhaust multiple same-account post-refresh transient retries before the request succeeds or terminates
- **THEN** the proxy MUST settle API-key usage before recording any deferred account-health failure
- **AND** each exhausted account MUST receive exactly one classified health failure plus one additional failure for every remaining exhausted retry
- **AND** selecting or exhausting a later account MUST NOT replace, lose, or duplicate an earlier account's deferred failures.

#### Scenario: Classified quota failures still use the model-capacity replay wait

- **WHEN** a replayable pre-created HTTP bridge request receives the selected-model capacity message with a quota or
  rate-limit error code
- **THEN** the proxy MUST preserve that quota or rate-limit classification for account health handling
- **AND** the proxy MUST still apply the model-capacity wait before replaying the request.
