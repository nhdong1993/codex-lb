## ADDED Requirements

### Requirement: HTTP-only streaming sources are served to WebSocket clients through an HTTP/SSE bridge

On both public Responses WebSocket route families and their trailing-slash equivalents, a source turn whose eligible candidates include no source declaring native Responses WebSocket support SHALL be served by issuing one streaming HTTP Responses request per turn to an eligible enabled streaming Responses source. When any eligible candidate declares native support, the native source session MUST be used as before. When the selected model has no eligible streaming Responses source, an unbound turn MUST keep failing with `model_source_requires_http_transport` after upgrade. A socket bound to a bridged session MUST keep its source, source revision, public model and bridged mode for later turns; a change MUST yield the existing `websocket_reconnect_required` error. Source authorization, assignments, aliases, overrides, ownership validation, subscription-anchor precedence, security routing, admission, quota reservation, request budgets and cleanup MUST be the same as for native source sessions.

The bridged HTTP request MUST NOT carry `type`, `generate` or a client-supplied `previous_response_id`, and MUST request streaming. Source SSE events of type `error` or `response.*` MUST be relayed to the client as WebSocket JSON text messages in source order, after model-identity restoration and durable ownership publication. Provider failure events MUST be sanitized as on native source sessions. SSE comments, `[DONE]` and other typed events MUST be dropped. Unparseable event data, events without a string type and events carrying `stream_id` MUST fail the turn with `model_source_invalid_event`. A body that ends before a terminal event MUST fail with `model_source_stream_truncated`. A source HTTP error before the stream MUST be delivered as a WebSocket `error` event carrying the HTTP route's redacted error envelope and status. An initial portable request MAY move to another eligible source only under the HTTP retry rules. When no replacement source is selectable, the last source error MUST be returned instead of a busy error; a bound bridged session MUST NOT move. A turn deadline that expires while the source request is opening MUST fail with 504 `model_source_timeout` after the request is closed, and MUST NOT be retried or replayed. The source HTTP response MUST be closed before the turn's admission is released. Request logs MUST record `transport=websocket` and `upstream_transport=openai_compatible_http`.

#### Scenario: A source-only key uses an HTTP-only source over WebSocket
- **GIVEN** a source-only key permitted to a streaming Responses model whose only source lacks native WebSocket support
- **WHEN** the client upgrades and sends `response.create` for that model
- **THEN** the upgrade is accepted, the source receives one streaming HTTP Responses request without `type`, `generate` or `previous_response_id`
- **AND** the client receives the source's `response.*` events in order with the public model identity
- **AND** the request log records `transport=websocket` and `upstream_transport=openai_compatible_http` and the reservation is settled once

#### Scenario: A non-streaming source still requires HTTP
- **GIVEN** a mixed key and a Responses source model without streaming support, which is not in the subscription model registry
- **WHEN** the client sends `response.create` for that model after the upgrade
- **THEN** the turn fails with `model_source_requires_http_transport` and no source request or reservation is made

#### Scenario: Native support is preferred
- **WHEN** an eligible candidate for the requested model declares native Responses WebSocket support
- **THEN** the turn uses the native source session and no bridged HTTP request is made

#### Scenario: A vendor event is not relayed
- **WHEN** the source stream contains a `codex.rate_limits` event or an SSE comment
- **THEN** the client does not receive it and the turn continues

#### Scenario: The source rejects the request before streaming
- **WHEN** the source answers the bridged HTTP request with status 429 or 5xx before any event
- **THEN** the client receives a WebSocket `error` event with that status and the redacted HTTP envelope
- **AND** the reservation is released and no subscription account receives the turn

#### Scenario: The only source rejects a portable first turn
- **GIVEN** one eligible HTTP-only streaming source for the model
- **WHEN** it answers a portable first bridged turn with status 429
- **THEN** the client receives that 429 envelope rather than `model_source_busy`, and the reservation is released once

#### Scenario: The turn deadline expires while the source request opens
- **WHEN** the remaining turn budget runs out before the source returns headers or its first event
- **THEN** the client receives 504 `model_source_timeout`, the request log records that timeout rather than a client departure, and no other source receives the turn

#### Scenario: The client leaves during a bridged turn
- **WHEN** the client disconnects while the source is streaming
- **THEN** the source HTTP response is closed before admission is released and the turn settles with the existing cancellation policy

### Requirement: Bridged continuation reconstructs full context per connection

A bridged session SHALL keep connection-local continuation state containing the response identifier of its most recently completed response, the complete input that turn was prepared from, and the output items of that response's `response.output_item.done` events as delivered. State MUST be replaced only by a `response.completed` terminal. Any other terminal, an error or a size overflow MUST clear it. When a later `response.create` on the same socket carries `previous_response_id` equal to that identifier, the proxy MUST replace the field by setting `input` to the stored input, then the stored output items, then the new input items, before routing, ownership validation and quota estimation run. A string input MUST be treated as one user message. After subscription-anchor, security-routing and ownership checks, which keep their precedence, any other client-supplied `previous_response_id` on a bridged turn MUST fail with the route's continuity classifier (`previous_response_not_found` on `/backend-api/codex/responses`, `stream_incomplete` on `/v1/responses`) with status 502, without contacting a source or reserving quota. The stored state MUST NOT exceed the Responses HTTP request-body limit, and an expanded request above it MUST be rejected with `invalid_request_error` before dispatch. State MUST NOT be shared across sockets or replicas.

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

### Requirement: Bridged warmups are answered locally

A bridged `response.create` with `generate:false` SHALL complete routing, policy and ownership preparation like any other turn. It MUST NOT reserve quota, MUST NOT contact a source, MUST NOT write a request-log row and MUST NOT record a dispatch result. Any admission claim it took MUST be released exactly once on every exit after preparation, including disconnect, drain or deadline expiry before the warmup runs. The client MUST receive `response.created` followed by `response.completed` for one new `resp_` identifier, with the public model, status `completed`, empty output and no usage. Before that completion is sent, the socket MUST be bound to the warmup's source, source revision, public model and bridged mode, and the identifier and warmup input MUST become the socket's continuation state.

#### Scenario: Codex prewarm on an HTTP-only source
- **WHEN** a client sends a `generate:false` create for a bridged model and then continues from the returned response with an empty input
- **THEN** the warmup produces no source request and no request-log row
- **AND** the continuation, sent immediately on the same socket, reaches the warmup's source with the warmup input as its full input and without a continuity error

#### Scenario: The client leaves before a prepared warmup runs
- **WHEN** a bridged warmup has completed preparation and the client disconnects or the server drains before the warmup is answered
- **THEN** its admission claim is released once and no reservation, provider request, request-log row or dispatch result is recorded

#### Scenario: Warmup policy errors are preserved
- **WHEN** a bridged warmup uses a forbidden model or a revoked key
- **THEN** it receives the same WebSocket domain error as a generating create

## MODIFIED Requirements

### Requirement: Source sessions implement a bounded sequential Responses profile

A source session SHALL support JSON text `response.create`, normal response events, tool-result continuation and `generate:false`. It MUST process at most one generation at a time, queue at most one later create, and reject excess creates without a reservation. Named `stream_id`, steering and application cancellation events MUST be rejected explicitly without changing an active turn; downstream disconnect SHALL cancel the session. HTTP-only envelope fields MUST NOT be sent upstream, and unsupported background execution MUST be rejected. Malformed, binary or oversized input and slow consumers MUST have bounded error/cleanup behavior. Idle sockets MUST NOT hold inference admission or quota reservations.

Queued work MUST hold no inference admission/reservation, MUST include queue time in its request deadline and MUST revalidate policy and identity at dequeue. Errors for rejected input MUST NOT reference or finalize an unrelated active generation. A successful no-generation warmup forwarded to a native source session MUST settle reported usage when present, or an input estimate with zero estimated output when absent; its reservation MUST use that no-output budget. A bridged warmup MUST instead follow the local-warmup requirement: no reservation, settlement, provider request or request-log row. Estimated usage MUST NOT be recorded as observed upstream usage. Warmup classification MUST use the final effective payload, and unexpected generated output from a native source MUST be withheld and treated as an invalid upstream response.

Every source-bound client message MUST use the same maximum of 16 MiB measured from its original UTF-8 JSON text, including the first create. Oversized creates MUST be rejected with `invalid_request_error` before inference admission, quota reservation or provider dispatch. A rejected initial create MUST leave the socket available for corrected input. Subscription-bound messages MUST retain their existing ingress limits.

#### Scenario: The first source create exceeds the native message limit
- **WHEN** a client submits a source create whose original JSON text exceeds 16 MiB on either route or trailing-slash equivalent
- **THEN** it receives `invalid_request_error` without a reservation or upstream call
- **AND** an identical create on an established source socket MUST be rejected by the same limit
- **AND** a subsequent bounded valid create MUST remain usable

#### Scenario: A new turn arrives immediately after completion
- **WHEN** the preceding terminal event has been sent but its settlement is pending
- **THEN** one subsequent create can wait and cannot dispatch before the preceding attempt has finalized

#### Scenario: Warmup has no generated output
- **WHEN** a native source returns a warmup response for `generate:false`
- **THEN** its returned references and usage follow normal ownership and accounting rules without fabricated generated output

#### Scenario: Warmup omits usage
- **WHEN** a limited-key no-generation warmup on a native source session succeeds without a usage object
- **THEN** it settles an input estimate and zero estimated output, while its request log does not claim observed usage

#### Scenario: Bridged warmup bypasses accounting
- **WHEN** a limited-key no-generation warmup is answered locally by a bridged session
- **THEN** no reservation is created or settled, no provider receives a request and no request-log row is written

#### Scenario: Source is disabled while work waits
- **WHEN** a create is queued and its source is disabled before dequeue
- **THEN** the queued request is denied without a reservation or upstream send and the preceding turn remains independently finalized

#### Scenario: An unsupported control does not interrupt a turn
- **WHEN** the client sends a named lane or steering/cancel event
- **THEN** the control receives an unsupported-operation error and is not forwarded or billed as a new generation

### Requirement: Source transport policy and health are scoped correctly

Explicit global HTTP transport SHALL retain ordinary handshake denial with HTTP 426. Under global auto/WebSocket policy, a streaming Responses source without native WebSocket support MUST be served through the HTTP/SSE bridge, and native upstream WebSocket MUST be used only for sources that declare it. A recent subscription WebSocket failure MUST NOT by itself deny a request routed to an authorized streaming Responses source. Source errors MUST NOT modify subscription account health or its global transport-failure marker. Source requests MUST NOT be sent to subscription accounts. After upgrade, failures MUST use WebSocket error envelopes rather than claim an HTTP handshake status was returned.

#### Scenario: One transport family fails
- **WHEN** the subscription transport failure marker is active and a permitted streaming Responses source is requested under auto mode
- **THEN** its native or bridged source session runs independently and its failures remain source-scoped

#### Scenario: An enforced subscription model cannot use the source exemption
- **WHEN** the subscription transport failure marker is active and effective key policy cannot select a streaming Responses source
- **THEN** an unrelated enabled source does not bypass the ordinary HTTP 426 handshake denial

#### Scenario: The operator pins HTTP transport
- **WHEN** the global upstream stream transport is `http`
- **THEN** ordinary WebSocket handshakes, including those for bridged sources, are refused with HTTP 426

### Requirement: Catalog WebSocket preference reflects authorized source capability

A source public model SHALL advertise WebSocket preference only when every authorized eligible equivalent source is an enabled streaming Responses source, served either natively or through the HTTP/SSE bridge, the runtime supports source forwarding and global policy permits it. Pools containing a non-streaming eligible source MUST remain conservative. Catalogs MUST NOT expose source identifiers, credentials or private alias mappings. An HTTP-only recorded owner MUST NOT be replaced by another source to satisfy a WebSocket preference.

Discovery eligibility MUST mean enabled Responses sources and enabled models permitted by the key, evaluated before filtering streaming capability.

Catalog and source-only installer WebSocket capability MUST reflect the model and source pool selected by effective key/model routing policy. Evaluation MUST preserve explicit raw source-alias precedence, canonical fallback, exact source model permissions and source assignment scope. Fast-mode prohibition MUST evaluate the canonical effective model instead of the prohibited alias. Model enforcement MUST be applied before capability evaluation. The complete eligible pool for that effective model MUST be checked before streaming filtering.

#### Scenario: A capable alias resolves to an HTTP-only effective source
- **GIVEN** a key enforces `gpt-5.4-fast`, its fast-alias source supports native WebSocket, and its `gpt-5.4` source streams Responses over HTTP only
- **WHEN** fast mode is prohibited
- **THEN** the source catalog preference and source-only installer MUST evaluate the `gpt-5.4` pool and enable WebSocket
- **AND** WebSocket turns for that effective request are bridged to the `gpt-5.4` source

#### Scenario: A streaming alias resolves to a non-streaming effective source
- **GIVEN** a key enforces `gpt-5.4-fast`, its fast-alias source streams, and its `gpt-5.4` source does not stream
- **WHEN** fast mode is prohibited
- **THEN** both the source catalog preference and source-only installer MUST disable WebSocket for that effective request

#### Scenario: An enforced alias falls back to a capable canonical source
- **GIVEN** a source-only key enforces `gpt-5.4-high`, no eligible source exposes that exact alias, and every eligible `gpt-5.4` source streams Responses
- **WHEN** global transport policy permits WebSocket
- **THEN** its installer MUST enable WebSocket using canonical source eligibility

#### Scenario: An HTTP-only streaming source prefers WebSocket
- **WHEN** the only authorized source for a public model streams Responses but lacks native WebSocket support
- **THEN** the catalog prefers WebSocket for that model and its turns are bridged

#### Scenario: Equivalent sources have mixed capabilities
- **WHEN** one authorized equivalent source supports native WebSocket and another supports only HTTP streaming
- **THEN** the catalog prefers WebSocket, WebSocket turns use the native source, and an anchored HTTP-only owner cannot be replaced during a WS request

### Requirement: Source-only handshakes honor effective HTTP-only capability

After successful authentication and firewall admission, ordinary Responses WebSocket handshakes for a source-only API key SHALL evaluate the same effective permitted model pool as its client installer. If that pool is empty or any eligible model is not an enabled streaming Responses model, the service MUST return HTTP 426 with the existing `websocket_upstream_transport_unavailable` envelope before accepting the socket, reserving usage or connecting upstream. A pool of streaming Responses models MUST retain WebSocket admission subject to existing transport policy, whether its sources are served natively or through the HTTP/SSE bridge. This rule MUST apply to both public Responses route families and trailing-slash variants. Mixed subscription/source and unrestricted keys MUST retain existing handshake policy. Required-capability routing MUST retain its existing WebSocket exception. A capability lookup failure MUST return a sanitized retryable HTTP 503 without accepting the socket or exposing internal failure details.

#### Scenario: HTTP-only streaming source keeps WebSocket

- **GIVEN** an authenticated source-only key assigned a streaming Responses model whose source lacks native WebSocket support
- **WHEN** a client requests a Responses WebSocket upgrade
- **THEN** the upgrade is accepted and the model's turns are bridged over HTTP/SSE
- **AND** an authorized HTTP request for that model continues to work

#### Scenario: HTTP-only source forces immediate transport fallback

- **GIVEN** an authenticated source-only key whose eligible pool contains an HTTP-only Responses model without streaming support
- **WHEN** a client requests a Responses WebSocket upgrade
- **THEN** the upgrade is rejected with HTTP 426 before any upstream attempt or usage reservation
- **AND** an authorized HTTP request for that model continues to work

#### Scenario: Capable source pool retains WebSocket

- **GIVEN** a source-only key whose effective permitted models all stream Responses
- **WHEN** an ordinary upgrade arrives and global transport permits WebSocket
- **THEN** the connection is accepted under the existing source routing policy

#### Scenario: Mixed key cannot be inferred from a later model frame

- **GIVEN** a key with both subscription accounts and a non-streaming source
- **WHEN** a model-less upgrade arrives
- **THEN** this source-only rule does not downgrade the key's subscription sessions

#### Scenario: Lookup failure is not evidence of HTTP-only capability

- **GIVEN** source capability lookup raises a database error or timeout
- **WHEN** a source-only handshake is evaluated
- **THEN** the service returns sanitized HTTP 503 without credentials or driver details

#### Scenario: Authentication precedes fallback

- **GIVEN** an invalid API key
- **WHEN** the client requests an upgrade
- **THEN** the normal authentication denial is returned instead of HTTP 426
