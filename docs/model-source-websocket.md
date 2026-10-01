# Model source WebSocket

Contract and operational details: [OpenSpec model-source-websocket](../openspec/specs/model-source-websocket/).

Model sources can opt into native Responses WebSocket. The provider must actually serve WebSocket on its Responses endpoint; HTTP/SSE streaming is insufficient.

1. Open **Settings → Advanced settings → Model sources** and edit the source.
2. Enable **Responses WebSocket**, **Responses** and **Streaming** for its model.
3. Save, then export a new client installer or configure the client to use WebSocket. An older exported installer retains its original transport flag.

The capability defaults off. Test the intended provider and client before enabling it in production. For `https://provider.example/v1`, the proxy connects to `wss://provider.example/v1/responses` using the configured source credential.

Clients can use `/v1/responses` or `/backend-api/codex/responses`, with or without the final slash. Sequential `response.create`, tool-result follow-ups and `generate:false` are supported. Each socket allows one active request and one waiting request. Named streams, steering, application cancellation and background responses are outside this initial profile; close the socket to cancel.

Each source message, including the first create, is limited to 16 MiB of UTF-8 JSON text. Whitespace and JSON escapes count toward this limit. An oversized create returns `invalid_request_error`; a smaller corrected request can use the same socket.

Reconnect after changing model, source or credentials. A reconnect preserves which source owns previous responses but cannot restore state held only by the old upstream socket. When that state is unavailable, start a new request with full context explicitly.

Source-only installers enable WebSocket only when their permitted Responses model set is nonempty and entirely capable. Mixed-capability pools retain HTTP preference. Global HTTP transport overrides source opt-in. Request logs show both WebSocket transports and the selected source.

Catalog and installer preferences follow the model selected after key enforcement and alias policy. For example, when fast mode is prohibited, `gpt-5.4-fast` uses the capability of the effective `gpt-5.4` source. Export a new installer after changing that policy.

For HA upgrades, deploy the runtime to every replica with the flag off, validate the provider, and then enable it. See [rollout and failure behavior](../openspec/specs/model-source-websocket/context.md).
