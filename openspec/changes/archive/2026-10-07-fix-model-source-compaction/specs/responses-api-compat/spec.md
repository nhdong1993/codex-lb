## ADDED Requirements

### Requirement: Compact source forwarding uses the Responses trigger contract

For a source-owned compact operation, the proxy MUST forward an HTTP Responses
request with `stream: true`, preserve the public model identity at the client
boundary, and send exactly one terminal `compaction_trigger` as the final input
item. It MUST use the source upstream model mapping only on the source wire.

The proxy MUST adapt a successful source stream containing an encrypted
`compaction` or `compaction_summary` output item to the established
`response.compaction` JSON result for standalone compact endpoints. It MUST
preserve a valid upstream compaction item ID, encrypted content, status and
reported input/output/cached/reasoning usage. It MUST return an existing OpenAI error
envelope for source failures and MUST NOT fabricate plaintext summaries.

Source compact attempts MUST settle or release API-key usage
exactly once, publish ownership before returning state-bearing output, and
close the source transport on error, cancellation and timeout. Request logs
MUST identify `request_kind=compaction`, the actual source and source revision
for source attempts.

#### Scenario: Encrypted source compaction is returned unchanged

- **WHEN** the source Responses stream completes with an encrypted compaction
  output item and usage
- **THEN** `/responses/compact` returns one normalized `type=compaction` item
- **AND** its encrypted content, valid `cmp_` ID and usage are preserved

#### Scenario: Trigger validation remains fail-fast

- **WHEN** a native Codex request contains duplicate or non-terminal trigger items
- **THEN** it returns the existing invalid-client-payload response
- **AND** no source, subscription account or reservation is used

#### Scenario: Source failure cleans up once

- **WHEN** source compaction fails, is cancelled or times out before a usable
  terminal response
- **THEN** the source transport and admission are closed
- **AND** the reservation is released or settled exactly once
- **AND** the request log records the source attempt as an error or cancellation, as appropriate

## MODIFIED Requirements

### Requirement: OpenAI-compatible sources route only compatible public routes

OpenAI-compatible model sources SHALL be eligible for public OpenAI-compatible
routes only when the source declares support for the route shape. Chat
Completions-compatible sources MAY serve `/v1/chat/completions`.
Responses-compatible sources MAY serve `/v1/responses` and
`/backend-api/codex/responses`. Audio-transcriptions-compatible sources MAY
serve `/v1/audio/transcriptions`. Responses sources MAY also serve HTTP compact
endpoints and terminal triggers under the source compaction requirements. File upload,
control-plane, and websocket bridge paths MUST remain subscription-backed unless
a later requirement explicitly defines OpenAI-compatible source behavior for
those paths.

#### Scenario: Chat completions routes to OpenAI-compatible source

- **GIVEN** an enabled OpenAI-compatible source declares chat-completions support
- **AND** the authenticated API key is allowed to use that source/model
- **WHEN** the client calls `POST /v1/chat/completions` with that model
- **THEN** the proxy forwards the request to the source's configured base URL
  using the source's upstream API key

#### Scenario: Codex-native Responses route uses Responses-compatible source

- **GIVEN** an enabled OpenAI-compatible source declares Responses support
- **AND** it exposes model `deepseek-v4-flash`
- **WHEN** a client calls `POST /backend-api/codex/responses` with model `deepseek-v4-flash`
- **THEN** the proxy forwards the request to that source's Responses endpoint

#### Scenario: Chat-only source is not used for Codex-native Responses route

- **GIVEN** an enabled OpenAI-compatible source exposes model `local-coder`
- **AND** the source declares Chat Completions support only
- **WHEN** a client calls `POST /backend-api/codex/responses` with model `local-coder`
- **THEN** the request is not routed to that source
- **AND** subscription-backed Codex routing rules continue to apply

#### Scenario: Compaction request is not source-routed

- **GIVEN** a Responses-compatible source exposes the requested model
- **AND** retained continuity is recorded for a subscription account
- **WHEN** the client sends a Codex terminal compaction trigger
- **THEN** it MUST remain on the subscription owner and MUST NOT contact the source

#### Scenario: HTTP compaction request retains source routing

- **GIVEN** an enabled Responses-compatible source exposes model `deepseek-v4-flash`
- **AND** a client calls `POST /backend-api/codex/responses` for that model whose
  input contains a `compaction_trigger` item
- **THEN** the request is forwarded to the external source with its upstream model mapping
- **AND** its retained state follows the same ownership checks as ordinary Responses

#### Scenario: V1 compaction_trigger remains eligible for model sources

- **GIVEN** an enabled Responses-compatible source exposes model `deepseek-v4-flash`
- **AND** a client calls `POST /v1/responses` for that model whose input ends with
  a terminal `compaction_trigger` item
- **THEN** the request remains eligible for that Responses-compatible source
- **AND** both HTTP route families preserve the selected source owner

#### Scenario: File-referencing request is not source-routed

- **GIVEN** an enabled Responses-compatible source exposes model `deepseek-v4-flash`
- **AND** a client calls `/backend-api/codex/responses` or `/v1/responses` for that
  model whose input references an uploaded `input_file`/`input_image` `file_id`
- **THEN** the request is not forwarded to the external source
- **AND** it follows the subscription path so the account-scoped file pin is honored

#### Scenario: Audio transcription routes to OpenAI-compatible source

- **GIVEN** an enabled OpenAI-compatible source declares audio transcriptions support
- **AND** it exposes model `whisper-large-v3`
- **WHEN** the client calls `POST /v1/audio/transcriptions` with multipart
  field `model=whisper-large-v3`
- **THEN** the proxy forwards the multipart request to the source's
  `/audio/transcriptions` endpoint
- **AND** the request uses the source's upstream API key

#### Scenario: Non-source transcription model keeps subscription validation

- **GIVEN** no audio-transcriptions-compatible source exposes model `gpt-4o-mini`
- **WHEN** the client calls `POST /v1/audio/transcriptions` with
  `model=gpt-4o-mini`
- **THEN** the proxy returns the existing unsupported transcription model error

### Requirement: Codex compaction triggers are bridged into compact output

When a subscription-owned `POST /backend-api/codex/responses` request has a top-level `input` array containing exactly one `{"type":"compaction_trigger"}` item as its final element, the proxy SHALL remove that trigger before calling upstream compaction handling and SHALL emit a raw SSE stream that contains exactly one compaction output item. The internal compact request built for that flow MUST contain exactly one terminal `compaction_trigger` item on the compact wire, and the proxy MUST reject duplicate or non-terminal top-level `compaction_trigger` placement locally with HTTP 400 `invalid_request_error` before any upstream compact handling.

The stream MUST emit `response.created`, `response.output_item.added`, `response.output_item.done`, and `response.completed` in that order with monotonically increasing sequence numbers. The added event MUST expose the selected compaction item as in progress. The done event and terminal completed response MUST carry the same terminal `compaction` item. When the selected encrypted upstream compaction item carries a valid `cmp_` ID or status, the synthetic stream MUST preserve those values with its `encrypted_content`; it MUST NOT generate or rewrite a replacement item ID. A malformed, empty, or non-`cmp_` ID MUST be omitted while the opaque encrypted content remains unchanged.

Subscription-owned Codex compact flows SHALL send the upstream compact request to `POST /backend-api/codex/responses` with `stream=true` and `store=false`, accept the upstream SSE response, and reconstruct one normalized compact response item from the terminal response lifecycle; they MUST NOT require the legacy `/backend-api/codex/responses/compact` upstream route to be available.

For subscription-owned Codex-affinity standalone compact requests, `POST /backend-api/codex/responses/compact` SHALL remain available as a compatibility endpoint with its subscription-backed compact routing contract, and SHALL normalize an upstream remote-compaction-v2 response that includes historical message output plus a compaction summary into the single compact output item required by Codex clients. A valid upstream `cmp_` compaction item `id` and any non-empty `status` MUST be preserved in that normalized output item. An empty, non-string, or non-`cmp_` ID MUST be omitted rather than rewritten; encrypted content MUST remain unchanged.

OpenAI-style `/v1/responses/compact` is otherwise unchanged by this requirement; when it receives duplicate top-level `compaction_trigger` items, codex-lb preserves the existing compatibility behavior and the forwarded compact input contains one terminal trigger.

Source-owned HTTP terminal triggers SHALL retain the source Responses SSE lifecycle and source ownership rules. Source-owned standalone compact requests SHALL use the source Responses trigger contract defined in this capability.

#### Scenario: terminal trigger emits a complete compact lifecycle

- **GIVEN** the compact request is subscription-owned
- **WHEN** a `POST /backend-api/codex/responses` request ends with exactly one top-level `compaction_trigger`
- **THEN** the proxy strips the trigger and invokes compact handling
- **AND** it emits created, added, done, and completed events in that order
- **AND** their sequence numbers increase monotonically from zero
- **AND** the done event and completed response contain the same single terminal compaction item

#### Scenario: terminal trigger becomes one compact-wire trigger

- **GIVEN** the compact request is subscription-owned
- **WHEN** a `POST /backend-api/codex/responses` request ends with exactly one
  top-level `compaction_trigger`
- **THEN** the proxy strips that trigger before compact-input preparation
- **AND** the internal compact request contains exactly one terminal
  `compaction_trigger` item on its `input` array

#### Scenario: encrypted compaction item identity survives trigger streaming

- **GIVEN** the compact request is subscription-owned
- **WHEN** compaction handling for a terminal trigger returns encrypted content with a non-empty upstream `cmp_*` ID and terminal status
- **THEN** the added event exposes that ID with in-progress status
- **AND** the done event and completed response preserve the exact upstream ID, terminal status, and encrypted content
- **AND** the proxy does not synthesize a replacement item ID

#### Scenario: malformed trigger placement is rejected

- **WHEN** a `POST /backend-api/codex/responses` or
  `POST /backend-api/codex/responses/compact` request contains duplicate or
  non-terminal top-level `compaction_trigger` items
- **THEN** the proxy returns HTTP 400 with `invalid_request_error`
- **AND** it does not attempt upstream compact handling

#### Scenario: Codex compact transport uses the Responses stream

- **WHEN** a valid terminal compaction trigger is submitted through a Codex
  compact flow
- **THEN** the proxy sends the compact request to
  `POST /backend-api/codex/responses` with `stream=true` and `store=false`
- **AND** it accepts the upstream SSE response and reconstructs one normalized
  compact response item from the terminal response lifecycle
- **AND** it does not require the legacy `/backend-api/codex/responses/compact`
  upstream route to be available

#### Scenario: Legacy message-shaped compact output does not get a rewritten item ID

- **WHEN** the upstream compact response exposes the encrypted compact payload
  as a legacy `message` item with a non-empty ID that does not begin with `cmp_`
- **THEN** the proxy converts that item to `type="compaction"` and omits the
  malformed ID
- **AND** the proxy preserves the encrypted content unchanged
- **AND** an existing ID that begins with `cmp_` is preserved byte-for-byte
- **AND** the proxy does not synthesize a `cmp_msg_...` ID
- **AND** ordinary message items outside the compact-output conversion remain
  unchanged

#### Scenario: Standalone Codex compact remains a compatibility endpoint

- **WHEN** a client calls `POST /backend-api/codex/responses/compact` for a subscription-owned request
- **THEN** codex-lb preserves the endpoint and its subscription-backed compact
  routing contract
- **AND** malformed duplicate or non-terminal top-level triggers are rejected
  locally before any upstream compact attempt

#### Scenario: Codex-affinity standalone compact normalizes remote v2 output

- **WHEN** a Codex-affinity `POST /backend-api/codex/responses/compact` request receives upstream output that contains historical message items and one compaction summary item
- **THEN** the JSON response body contains exactly one `output` item for that compaction summary
- **AND** the normalized item preserves the compaction summary's valid `cmp_`-prefixed upstream ID and status
- **AND** it does not expose historical message items as standalone compact output

#### Scenario: OpenAI-compatible compact normalizes duplicate triggers

- **WHEN** a client calls `POST /v1/responses/compact` with duplicate
  top-level `compaction_trigger` items
- **THEN** codex-lb preserves the existing compatibility behavior and returns
  HTTP 200 when the compact operation succeeds
- **AND** the forwarded compact input contains one terminal trigger

### Requirement: A disabled model source refuses its models instead of falling through

The system SHALL NOT dispatch to a subscription account a request whose model
is served by an OpenAI-compatible model source that an operator has switched
off. It SHALL refuse such a request with HTTP status `503` and error code
`model_source_disabled`.

"Switched off" covers both a disabled source row and a disabled model row on an
enabled source. The refusal SHALL apply on `/v1/chat/completions`,
`/v1/responses`, `/backend-api/codex/responses`, and both HTTP compact endpoints.

The refusal SHALL be decided by the ordinary source-selection rules with the
enabled-state filter inverted and nothing else changed: same candidate list
(raw client alias and normalized model), same API key model allowlist, same
source assignment scope, same subscription-registry precedence, same route
shape, same streaming requirement. A request that the ordinary lookup would
have missed for any reason other than enabled state MUST keep its existing
behaviour, including a model no source exposes, a source the API key is not
assigned to, a chat-only source asked for a Responses route, and a
subscription-registry slug that an unscoped API key never source-routes.

Requests pinned to the subscription account that received an uploaded file
MUST retain their subscription route. WebSocket structural compaction exclusions
remain unchanged. HTTP terminal triggers MUST follow the source enablement check.

The WebSocket source preflight SHALL refuse an opted-in source or model that is disabled with `model_source_disabled` before reservation. Sources without native capability SHALL retain `model_source_requires_http_transport`. An established native source session SHALL revalidate enablement before dispatching another turn. Structural subscription exclusions and recorded subscription owners SHALL retain their precedence.

The refusal MUST happen before any usage reservation is taken, so a refused
request strands no reservation, and MUST NOT create a request log entry for a
dispatch that never happened.

#### Scenario: Chat request for a disabled source's model is refused

- **GIVEN** an OpenAI-compatible model source exposes model `m` and is disabled
- **WHEN** a client calls `POST /v1/chat/completions` with model `m`
- **THEN** the response is `503` with error code `model_source_disabled`
- **AND** no subscription account is selected for the request
- **AND** no usage reservation is left held

#### Scenario: Responses request for a disabled source's model is refused

- **GIVEN** a Responses-capable OpenAI-compatible model source exposes model `m` and is disabled
- **WHEN** a client calls `POST /v1/responses` or `POST /backend-api/codex/responses` with model `m`
- **THEN** the response is `503` with error code `model_source_disabled`
- **AND** no subscription account is selected for the request

#### Scenario: A disabled model on an enabled source is refused

- **GIVEN** an enabled OpenAI-compatible model source whose model row for `m` is disabled
- **WHEN** a client calls `POST /v1/chat/completions` with model `m`
- **THEN** the response is `503` with error code `model_source_disabled`

#### Scenario: A model no source exposes is unaffected

- **GIVEN** no model source exposes model `m`, enabled or disabled
- **WHEN** a client calls `POST /v1/chat/completions` with model `m`
- **THEN** subscription routing proceeds exactly as it did before this requirement

#### Scenario: A WebSocket turn for a disabled source's model bounces to HTTP

- **GIVEN** an HTTP-only Responses-capable model source exposes model `m` and is disabled
- **WHEN** a client requests model `m` over the WebSocket transport, at connect time or on a later turn over an already-open socket
- **THEN** the turn is refused with the service-level `model_source_requires_http_transport` failure
- **AND** the turn is not forwarded to a subscription account upstream

#### Scenario: A subscription slug shadowed by a disabled source is unaffected

- **GIVEN** a disabled OpenAI-compatible model source lists a slug the subscription model registry already serves
- **AND** an API key without source assignment scoping
- **WHEN** the key requests that slug
- **THEN** the request is not refused with `model_source_disabled`
- **AND** subscription routing proceeds unchanged
