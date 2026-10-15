## MODIFIED Requirements

### Requirement: Previous-response source routing follows proven ownership

When a Responses request targets a configured Responses-compatible model source and carries `previous_response_id`, the proxy MUST use recorded subscription-account ownership as the veto for model-source routing. The proxy MUST NOT infer ownership from the response identifier's syntax. A recorded subscription owner MUST keep the request on subscription routing, except for a source-only model on the direct Responses WebSocket transport as defined below. When no subscription owner is recorded, the configured model source MUST remain authoritative, including when the identifier uses the canonical OpenAI `resp_` hexadecimal shape.

For the direct Responses WebSocket transport, a recorded subscription owner MUST keep the request on the owner-bound subscription path unless the requested model is source-only. A configured source model without a recorded subscription owner SHALL use the native source WebSocket path only when the source and model are eligible under `model-source-websocket`; otherwise it MUST retain `model_source_requires_http_transport`.

A requested model is source-only when an enabled or disabled Responses-capable model source claims it under the ordinary source-selection rules and none of the request's model candidates (the raw client model, or the API key's enforced model when one is set, and the normalized model) is in the subscription model registry. On the direct Responses WebSocket transport, recorded subscription-account continuity MUST NOT dispatch a source-only turn to a subscription account. Recorded continuity means the recorded subscription owner of `previous_response_id`, or the subscription account that owns the request's client-supplied turn-state alias under the requesting API key. This MUST hold on the first turn of a socket and on a socket already bound to a subscription account by an earlier turn, including a `generate:false` warmup. On a socket bound to a native source session, such a turn is not a source/subscription backend change and MUST receive the same refusal instead of `websocket_reconnect_required`. The proxy MUST refuse such a turn with the service-level failure `model_source_requires_http_transport` (status 503), MUST NOT forward it to a model source over WebSocket, and MUST NOT leave a usage reservation held for it.

When any model candidate is in the subscription model registry, including a registry slug that a source-scoped API key routes to an assigned source, a recorded subscription owner MUST keep the owner-bound subscription precedence above and the proxy MUST NOT emit `model_source_requires_http_transport` for that reason. Structural subscription exclusions (a terminal `compaction_trigger` and uploaded `input_file` references) and required-capability security routing MUST retain their precedence over the source-only refusal. HTTP Responses routes MUST keep the recorded-owner veto as specified above.

#### Scenario: Recorded subscription owner overrides an HTTP model source

- **GIVEN** a Responses-compatible source is configured for the requested model
- **AND** request logs record a subscription account as the owner of `previous_response_id`
- **WHEN** the client calls `/backend-api/codex/responses` or `/v1/responses`
- **THEN** the request is not forwarded to the model source
- **AND** subscription routing preserves the recorded account owner

#### Scenario: Canonical source response ID remains source-routed over HTTP

- **GIVEN** a Responses-compatible source is configured for the requested model
- **AND** no subscription account is recorded as owner of `previous_response_id`
- **AND** `previous_response_id` uses a canonical OpenAI-compatible `resp_` hexadecimal shape
- **WHEN** the client calls `/backend-api/codex/responses` or `/v1/responses`
- **THEN** the request is forwarded to the configured model source

#### Scenario: Direct WebSocket preserves a recorded subscription owner

- **GIVEN** an API key with source assignment scoping is assigned a source that serves a subscription-registry model
- **AND** request logs record a subscription account as the owner of `previous_response_id`
- **WHEN** a direct Responses WebSocket client submits the follow-up for that registry model
- **THEN** the request remains on the owner-bound subscription WebSocket path
- **AND** the proxy does not emit `model_source_requires_http_transport`

#### Scenario: Direct WebSocket source continuation falls back to HTTP

- **GIVEN** a source without native WebSocket capability is configured for the requested model
- **AND** no subscription account is recorded as owner of `previous_response_id`
- **AND** `previous_response_id` uses a canonical OpenAI-compatible `resp_` hexadecimal shape
- **WHEN** a direct Responses WebSocket client submits the follow-up
- **THEN** the proxy emits `model_source_requires_http_transport`
- **AND** the request is not sent to a subscription upstream

#### Scenario: Source-only follow-up after a subscription warmup falls back to HTTP

- **GIVEN** an API key without source assignment scoping
- **AND** an HTTP-only Responses-capable source serves model `m`, which is not in the subscription model registry
- **AND** a direct Responses WebSocket client completed a `generate:false` warmup for a subscription-registry model on a subscription account
- **WHEN** the client sends `response.create` for `m` on the same socket with `previous_response_id` set to the warmup response
- **THEN** the turn is refused with the service-level `model_source_requires_http_transport` failure and status 503
- **AND** the turn is not sent to the subscription upstream or to the model source
- **AND** no usage reservation remains held

#### Scenario: Recorded subscription owner does not pin a source-only first turn

- **GIVEN** a Responses-capable source serves model `m`, which is not in the subscription model registry
- **AND** request logs record a subscription account as the owner of `previous_response_id`
- **WHEN** a direct Responses WebSocket client sends that follow-up for `m` as the first turn on a new socket
- **THEN** the turn is refused with the service-level `model_source_requires_http_transport` failure and status 503
- **AND** no subscription account receives the turn
- **AND** the turn is not forwarded to the source over WebSocket, even when the source supports native WebSocket

#### Scenario: Turn-state owner does not pin a source-only turn

- **GIVEN** a Responses-capable source serves model `m`, which is not in the subscription model registry
- **AND** the WebSocket request carries a client-supplied `x-codex-turn-state` alias owned by a subscription account under the requesting API key
- **WHEN** a direct Responses WebSocket client sends `response.create` for `m`
- **THEN** the turn is refused with the service-level `model_source_requires_http_transport` failure and status 503
- **AND** no subscription account receives the turn

#### Scenario: Source-bound socket refuses a subscription-anchored source-only turn

- **GIVEN** a direct Responses WebSocket socket is bound to a native source session for model `m`, which is not in the subscription model registry
- **AND** request logs record a subscription account as the owner of response `resp_x`
- **WHEN** the client sends `response.create` for `m` with `previous_response_id` `resp_x` on the same socket
- **THEN** the turn is refused with the service-level `model_source_requires_http_transport` failure and status 503 rather than `websocket_reconnect_required`
- **AND** neither the subscription upstream nor the source receives the turn

#### Scenario: Structural exclusion keeps precedence over the source-only refusal

- **GIVEN** a Responses-capable source serves model `m`, which is not in the subscription model registry
- **AND** request logs record a subscription account as the owner of `previous_response_id`
- **WHEN** a direct Responses WebSocket client sends `response.create` for `m` whose input ends with a terminal `compaction_trigger`
- **THEN** the proxy does not emit `model_source_requires_http_transport`
- **AND** the turn follows the recorded subscription owner

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

The WebSocket source preflight SHALL refuse an opted-in source or model that is disabled with `model_source_disabled` before reservation. Sources without native capability SHALL retain `model_source_requires_http_transport`. An established native source session SHALL revalidate enablement before dispatching another turn. Structural subscription exclusions SHALL retain their precedence. Recorded subscription owners SHALL retain their precedence, except that a WebSocket turn for a source-only model MUST be refused with `model_source_requires_http_transport` as defined in "Previous-response source routing follows proven ownership".

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

#### Scenario: A subscription owner does not pin a disabled source-only model over WebSocket

- **GIVEN** a Responses-capable model source exposes model `m`, which is not in the subscription model registry, and is disabled
- **AND** request logs record a subscription account as the owner of `previous_response_id`
- **WHEN** a client continues with model `m` over the WebSocket transport
- **THEN** the turn is refused with the service-level `model_source_requires_http_transport` failure
- **AND** the turn is not forwarded to a subscription account upstream

#### Scenario: A subscription slug shadowed by a disabled source is unaffected

- **GIVEN** a disabled OpenAI-compatible model source lists a slug the subscription model registry already serves
- **AND** an API key without source assignment scoping
- **WHEN** the key requests that slug
- **THEN** the request is not refused with `model_source_disabled`
- **AND** subscription routing proceeds unchanged
