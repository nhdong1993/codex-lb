## MODIFIED Requirements

### Requirement: Source WebSocket routes retain source authorization and payload semantics

Both `/v1/responses` and `/backend-api/codex/responses`, including explicit trailing-slash equivalents without redirect, SHALL support opted-in source requests. Routing MUST apply raw/enforced public-model policy, source assignments, per-source overrides and aliases before dispatch. It MUST preserve source HTTP reasoning/instruction/tool semantics and validate original and effective ownership references. Subscription-owned anchors, uploaded-file ownership and required-capability security rules MUST retain their precedence over source dispatch. A terminal `compaction_trigger` MUST NOT by itself exclude a turn from source dispatch: on native and bridged source sessions a compaction turn MUST follow the same routing, ownership, continuation, admission, reservation, settlement and relay rules as any other turn, except that a completed bridged compaction response MUST NOT become continuation state, MUST stay on the socket's bound source session without `websocket_reconnect_required`, and its request log MUST record `request_kind=compaction`. Unless a structural subscription exclusion or required-capability security routing applies, which keep their precedence, a subscription-owned anchor for a source-only model MUST NOT route the turn to a subscription account and MUST yield `model_source_requires_http_transport` as defined in `responses-api-compat`. Lookup failure MUST fail closed before reservation or upstream dispatch.

Domain errors raised during shared preparation or source quota reservation MUST retain the existing WebSocket error status, type, code, message and supplied parameter. This contract MUST also apply when the eventual backend is subscription and when no model source is configured.

Shared source ownership preparation MUST preserve the existing HTTP error envelope on both Responses route families and their trailing-slash equivalents. An unavailable recorded source owner MUST return status 409 with type `server_error` and code `previous_response_owner_unavailable` when `previous_response_id` is present, or `model_source_owner_unavailable` for other owned references. This contract MUST apply regardless of the source's WebSocket capability; WebSocket adaptation MUST retain the same ownership-error envelope.

#### Scenario: A recorded source owner becomes unavailable
- **GIVEN** an HTTP source response published a response or output-item reference
- **WHEN** the source is disabled and the client continues using that reference over HTTP or WebSocket
- **THEN** the shared ownership check MUST retain the 409 `server_error` envelope and the reference-appropriate error code
- **AND** the rejected turn MUST NOT reserve quota, acquire source admission or reach any provider

#### Scenario: Shared preparation rejects key policy
- **WHEN** a create on either public WebSocket route or trailing-slash equivalent uses a revoked key or a forbidden model or reasoning effort
- **THEN** it MUST retain the established authentication or permission error type and any parameter such as `reasoning.effort`
- **AND** no rejected request reaches a provider or acquires quota

#### Scenario: Source quota is exhausted
- **WHEN** source quota reservation rejects an initial or subsequent create with a rate-limit domain error
- **THEN** its WebSocket error MUST retain status 429 and `rate_limit_error`, consistent with HTTP Responses
- **AND** the rejected turn MUST release admission without creating a reservation or sending an upstream request

#### Scenario: Source alias reaches the selected provider
- **WHEN** an authorized create requests a source alias over either public WS path
- **THEN** only its selected source receives its mapped upstream model and source credential
- **AND** the client and accounting retain the public model identity

#### Scenario: Overrides cannot bypass file ownership
- **WHEN** a source override introduces an account-scoped file reference
- **THEN** the request is rejected before source reservation or dispatch and is not redirected using stale pre-override state

#### Scenario: Failed source lookup does not select an account
- **WHEN** source routing or ownership lookup fails
- **THEN** the turn receives an error, no subscription/source attempt is made, and no quota reservation remains

#### Scenario: A turn inherits a required capability
- **WHEN** a create carries a session, turn, parent-task or previous-response alias with a durable required capability, including an alias introduced by its effective source payload
- **THEN** capability routing takes precedence before any source admission or reservation
- **AND** unavailable lineage lookup fails closed and no source receives the turn

#### Scenario: A reconnect carries a subscription-owned turn state
- **WHEN** a create carries an explicit turn-state alias owned by a subscription account under the exact API key, including without a previous response ID
- **THEN** the source path MUST preserve subscription ownership or fail closed before source admission
- **AND** conflicting or unavailable ownership lookup MUST NOT permit source dispatch, while an unregistered synthesized source placeholder MUST remain usable

#### Scenario: A subscription anchor cannot pin a source-only model
- **WHEN** a create for a source-only model (claimed by a source, with no model candidate in the subscription model registry) carries a subscription-owned previous-response or turn-state anchor
- **AND** no structural subscription exclusion or required-capability routing applies
- **THEN** the turn MUST receive the service-level `model_source_requires_http_transport` failure
- **AND** neither a subscription account nor the source receives the turn, and no usage reservation remains held

#### Scenario: A first-turn compaction reaches an HTTP-only source
- **GIVEN** a source-only key permitted to a streaming Responses model whose only source lacks native WebSocket support
- **WHEN** the first `response.create` on a socket for that model has input ending with a terminal `compaction_trigger`
- **THEN** the source receives one streaming HTTP Responses request whose input ends with that trigger
- **AND** the client receives the source's compaction output item and `response.completed` with the public model identity
- **AND** no subscription account receives the turn, and the request log records `transport=websocket`, `upstream_transport=openai_compatible_http` and `request_kind=compaction`

#### Scenario: A compaction continues a bound bridged session
- **GIVEN** a bridged socket whose last completed response `resp_1` had input `[U1]` and delivered output item `M1`
- **WHEN** the client sends `response.create` with `previous_response_id` `resp_1` and input `[compaction_trigger]`
- **THEN** the same source receives input `[U1, M1, compaction_trigger]` without `previous_response_id`
- **AND** the client does not receive `websocket_reconnect_required`

#### Scenario: A native source session serves a compaction turn
- **WHEN** a create whose input ends with a terminal `compaction_trigger` is routed to a source that declares native Responses WebSocket support
- **THEN** the native source session forwards it to that source and relays its terminal event to the client

#### Scenario: An invalid first subscription create is corrected
- **WHEN** shared or subscription-specific payload validation rejects the first create before backend preparation succeeds
- **THEN** the socket remains available for a corrected create without becoming bound to either backend

### Requirement: Bridged continuation reconstructs full context per connection

A bridged session SHALL keep connection-local continuation state containing the response identifier of its most recently completed response, the complete input that turn was prepared from, and the output items of that response's `response.output_item.done` events as delivered. State MUST be replaced only by a `response.completed` terminal of a turn whose input does not end with a terminal `compaction_trigger`. Any other terminal, a completed compaction turn, an error or a size overflow MUST clear it. When a later `response.create` on the same socket carries `previous_response_id` equal to that identifier, the proxy MUST replace the field by setting `input` to the stored input, then the stored output items, then the new input items, before routing, ownership validation and quota estimation run. A string input MUST be treated as one user message. After subscription-anchor, security-routing and ownership checks, which keep their precedence, any other client-supplied `previous_response_id` on a bridged turn MUST fail with the route's continuity classifier (`previous_response_not_found` on `/backend-api/codex/responses`, `stream_incomplete` on `/v1/responses`) with status 502, without contacting a source or reserving quota. The stored state MUST NOT exceed the Responses HTTP request-body limit, and an expanded request above it MUST be rejected with `invalid_request_error` before dispatch. State MUST NOT be shared across sockets or replicas.

#### Scenario: A tool result continues a bridged response
- **GIVEN** a bridged turn with input `[U1]` completed as `resp_1` after delivering output items `rs_1` and `fc_1` with `call_id` `call_1`
- **WHEN** the client sends `previous_response_id: resp_1` and input `[function_call_output(call_1)]` on the same socket
- **THEN** the source receives input `[U1, rs_1, fc_1, function_call_output(call_1)]` without `previous_response_id`
- **AND** ownership validation pins the request to the source and revision that produced `resp_1`

#### Scenario: An unknown continuation fails closed
- **WHEN** a bridged turn carries a `previous_response_id` that is not the socket's last completed bridged response
- **THEN** the client receives the route's continuity error and no source request or reservation is made

#### Scenario: A failed response cannot be continued
- **WHEN** a bridged response ends with `response.failed` or `response.incomplete` and the client then references it
- **THEN** the reference fails with the continuity error

#### Scenario: A compaction response cannot be continued
- **GIVEN** a bridged compaction turn with input `[U1, compaction_trigger]` completed as `resp_c` after delivering compaction item `C1`
- **WHEN** the client sends `response.create` with `previous_response_id` `resp_c` and input `[U2]`
- **THEN** the client receives the route's continuity error with status 502 and no source request or reservation is made
- **AND** a full resend of `[C1, U2]` without `previous_response_id` reaches the source unchanged
