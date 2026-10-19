## MODIFIED Requirements

### Requirement: Previous-response source routing follows proven ownership

When a Responses request targets a configured Responses-compatible model source and carries `previous_response_id`, the proxy MUST use recorded subscription-account ownership as the veto for model-source routing. The proxy MUST NOT infer ownership from the response identifier's syntax. A recorded subscription owner MUST keep the request on subscription routing, except for a source-only model on the direct Responses WebSocket transport as defined below. When no subscription owner is recorded, the configured model source MUST remain authoritative, including when the identifier uses the canonical OpenAI `resp_` hexadecimal shape.

For the direct Responses WebSocket transport, a recorded subscription owner MUST keep the request on the owner-bound subscription path unless the requested model is source-only. A configured source model without a recorded subscription owner SHALL use the native source WebSocket session when an eligible source declares native support, and the HTTP/SSE bridge otherwise, as defined under `model-source-websocket`. A bridged turn MUST NOT forward a client-supplied `previous_response_id`. One that does not name the socket's last completed bridged response MUST receive the route's continuity error (`previous_response_not_found` on `/backend-api/codex/responses`, `stream_incomplete` on `/v1/responses`, status 502) and MUST NOT be sent to a source or a subscription account.

A requested model is source-only when an enabled or disabled Responses-capable model source claims it under the ordinary source-selection rules and none of the request's model candidates (the raw client model, or the API key's enforced model when one is set, and the normalized model) is in the subscription model registry. On the direct Responses WebSocket transport, recorded subscription-account continuity MUST NOT dispatch a source-only turn to a subscription account. Recorded continuity means the recorded subscription owner of `previous_response_id`, or the subscription account that owns the request's client-supplied turn-state alias under the requesting API key. This MUST hold on the first turn of a socket and on a socket already bound to a subscription account by an earlier turn, including a `generate:false` warmup. On a socket bound to a native or bridged source session, such a turn is not a source/subscription backend change and MUST receive the same refusal instead of `websocket_reconnect_required`. The proxy MUST refuse such a turn with the service-level failure `model_source_requires_http_transport` (status 503), MUST NOT forward it to a model source over WebSocket, and MUST NOT leave a usage reservation held for it.

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

- **GIVEN** a Responses source that does not support streaming is configured for the requested model, which is not in the subscription model registry
- **AND** no subscription account is recorded as an owner of the request's references
- **WHEN** a direct Responses WebSocket client submits a follow-up that resends its full context without `previous_response_id`
- **THEN** the proxy emits `model_source_requires_http_transport`
- **AND** the request is not sent to a subscription upstream

#### Scenario: Direct WebSocket source continuation without connection state fails closed

- **GIVEN** a streaming source without native WebSocket capability is configured for the requested model
- **AND** no subscription account is recorded as owner of `previous_response_id`
- **AND** `previous_response_id` uses a canonical OpenAI-compatible `resp_` hexadecimal shape and is not the socket's last completed bridged response
- **WHEN** a direct Responses WebSocket client submits the follow-up
- **THEN** the proxy emits the route's continuity error with status 502
- **AND** the request is not sent to a subscription upstream or to the source

#### Scenario: Direct WebSocket source continuation is bridged

- **GIVEN** a streaming source without native WebSocket capability served the socket's last completed response `resp_1`
- **WHEN** the client sends `response.create` with `previous_response_id` `resp_1` and new input items
- **THEN** the source receives one HTTP Responses request with the reconstructed full input and no `previous_response_id`
- **AND** the proxy does not emit `model_source_requires_http_transport`

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

- **GIVEN** a direct Responses WebSocket socket is bound to a native or bridged source session for model `m`, which is not in the subscription model registry
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
