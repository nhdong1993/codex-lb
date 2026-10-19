## Why

Codex clients keep one Responses WebSocket per session. A model source that only implements HTTP/SSE Responses, such as `ch-relay (VPS)` serving `ch-relay/gpt-6-astra`, cannot take those turns today:

- a source-only key whose pool is not entirely native-WebSocket capable is refused at the handshake with HTTP 426, so Codex downgrades the whole session to HTTP;
- a mixed or unrestricted key is accepted, and the first source turn then fails after the upgrade with `model_source_requires_http_transport`.

The client should keep its WebSocket while codex-lb keeps talking HTTP/SSE to the source. Native WebSocket support at the provider is not needed for that: codex-lb can terminate the client WebSocket and issue one ordinary streaming HTTP request per turn.

The difficulty is continuation. Over WebSocket, Codex sends `previous_response_id` together with only the input items added since the previous response. An HTTP-only source keeps no response state for that id (Codex sends `store: false`), so the proxy has to rebuild the full input before each HTTP request.

## What Changes

- Serve Responses WebSocket turns for streaming Responses sources that do not declare native WebSocket through an HTTP/SSE bridge on both public route families. Sources that declare `supports_responses_websocket` keep the native WebSocket path, which is preferred when an eligible candidate supports it.
- Keep a connection-local transcript for bridged sessions: the full input of the last completed response plus its `response.output_item.done` items. A `previous_response_id` naming that response is replaced by the full input before dispatch. Any other `previous_response_id` gets the existing continuity error without contacting the source. The proxy never forwards a client `previous_response_id` to a bridged source.
- Answer bridged `generate:false` warmups locally, after normal routing and policy checks, with no reservation, source request or request-log row.
- Relay source SSE `response.*` and `error` events as WebSocket JSON messages with the native session's validation, sanitization, ownership publication and settlement. Other typed vendor events, SSE comments and `[DONE]` are dropped.
- Treat every enabled streaming Responses source model as WebSocket-capable for catalog `prefer_websockets`, the source-only handshake decision and the source-only installer flag. Non-streaming pools keep the HTTP 426 path.
- Log bridged turns with `transport=websocket` and `upstream_transport=openai_compatible_http`.
- **BREAKING (client-visible transport)**: source-only keys whose pools are HTTP-only are no longer refused with 426, and mixed keys no longer receive `model_source_requires_http_transport` for HTTP-only source models outside subscription anchors. Installers exported before this change keep their embedded HTTP flag until re-exported.

## Capabilities

### Modified Capabilities

- `model-source-websocket`: add the HTTP/SSE bridge, bridged continuation and bridged warmup requirements; widen transport policy, catalog preference and source-only handshake capability from native WebSocket to streaming Responses.
- `responses-api-compat`: replace the HTTP-required error for source continuations without a subscription owner with the bridged continuation contract. Subscription-anchored source-only turns keep `model_source_requires_http_transport`.
- `api-key-dashboard`: source-only installers enable WebSockets when the eligible Responses set is entirely streaming.

## Impact

- Backend: `app/modules/proxy/source_websocket.py` (bridge relay, transcript, warmup), `app/modules/proxy/api.py` (mode selection, HTTP opener, handshake capability), `app/modules/model_sources/catalog.py` (capability), `app/modules/proxy/source_dispatch.py` (discard latch for local warmups).
- No migration, no new `CODEX_LB_*` setting, no API schema change, no dashboard change. The existing `supports_responses_websocket` flag keeps its meaning: native upstream WebSocket.
- Kill switch: the existing dashboard upstream stream transport `http` still refuses every ordinary WebSocket handshake with 426.
- Tests: new public-route integration tests against a local HTTP/SSE stub; existing tests that pinned 426 or `model_source_requires_http_transport` for HTTP-only sources are updated.
- Docs: `docs/model-source-websocket.md` and the capability context.

## Non-goals

- Bridging non-streaming sources or Chat Completions sources.
- Forwarding `previous_response_id` to HTTP sources with stored-response support, or resuming a transcript after reconnect, on another replica or across sockets.
- Multiplexed `stream_id` lanes, steering, `response.cancel` and background responses (still rejected).
- Application heartbeats on bridged turns (the native source session has none either).
- Raising the existing 16 MiB limit on the first source create message.
- Dashboard label changes for the native WebSocket checkbox.
