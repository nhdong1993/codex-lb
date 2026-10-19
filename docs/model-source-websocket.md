# Model source WebSocket

Contract and operational details: [OpenSpec model-source-websocket](../openspec/specs/model-source-websocket/).

Clients can talk Responses WebSocket to any streaming Responses model source. How codex-lb reaches the source depends on the source:

- **Native**: the source has **Responses WebSocket** enabled. codex-lb keeps one upstream WebSocket per client socket.
- **Bridged**: every other streaming Responses source. codex-lb keeps the client WebSocket and sends one streaming HTTP Responses request (`POST …/responses`, SSE) per turn. No setting is needed.

Clients can use `/v1/responses` or `/backend-api/codex/responses`, with or without the final slash. Sequential `response.create`, tool-result follow-ups and `generate:false` are supported. Each socket allows one active request and one waiting request. Named streams, steering, application cancellation and background responses are not supported; close the socket to cancel.

## Enabling native WebSocket

The provider must actually serve WebSocket on its Responses endpoint; HTTP/SSE streaming is insufficient.

1. Open **Settings → Advanced settings → Model sources** and edit the source.
2. Enable **Responses WebSocket**, **Responses** and **Streaming** for its model.
3. Save. For `https://provider.example/v1`, the proxy connects to `wss://provider.example/v1/responses` using the configured source credential.

The capability defaults off. Test the intended provider and client before enabling it in production. When a model has both native and HTTP-only sources, WebSocket turns use the native ones.

## Bridged HTTP-only sources

Over WebSocket, Codex sends `previous_response_id` and only the input added since its last response. An HTTP-only source keeps no such state, so codex-lb rebuilds the request for each continuation of the socket's last completed bridged response. The rebuilt input is the previous input, then that response's output items, then the new items. The source never receives `previous_response_id`. A `generate:false` warmup is answered by codex-lb itself: it creates no source request, no reservation and no request-log row.

The rebuilt context lives only on that socket and that replica. A `previous_response_id` that is not the socket's last completed response fails with the usual continuity error (`previous_response_not_found` on `/backend-api/codex/responses`, `stream_incomplete` on `/v1/responses`). Codex then retries with full input. The same happens after reconnects, deploys and failed or incomplete responses. The rebuilt context is bounded by the Responses HTTP request-body limit.

Request logs show `transport=websocket` with `upstream_transport=openai_compatible_http` for bridged turns, and `openai_compatible_websocket` for native ones.

## Limits, installers and rollout

Each source message, including the first create, is limited to 16 MiB of UTF-8 JSON text. Whitespace and JSON escapes count toward this limit. An oversized create returns `invalid_request_error`; a smaller corrected request can use the same socket.

Reconnect after changing model, source or credentials. A reconnect preserves which source owns previous responses but cannot restore state held only by the old socket. When that state is unavailable, start a new request with full context.

Source-only installers enable WebSocket only when their permitted Responses model set is nonempty and every model streams. A model without streaming keeps HTTP and is refused with HTTP 426 at a source-only WebSocket handshake. Request logs show the transports and the selected source. An older exported installer retains its original transport flag; export a new installer to switch a source-only key from HTTP to WebSocket.

Setting the global upstream stream transport to `http` refuses every ordinary WebSocket handshake with 426. Use it as the switch to send all clients back to HTTP, including bridged sessions.

Catalog and installer preferences follow the model selected after key enforcement and alias policy. For example, when fast mode is prohibited, `gpt-5.4-fast` uses the capability of the effective `gpt-5.4` source. Export a new installer after changing that policy.

For HA upgrades, deploy the runtime to every replica, then validate the provider before enabling native WebSocket on a source. See [rollout and failure behavior](../openspec/specs/model-source-websocket/context.md).
