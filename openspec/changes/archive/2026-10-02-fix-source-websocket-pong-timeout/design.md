## Context

The source transport used the `websockets` client defaults, including a 20-second pong deadline. CLIProxyAPI can continue writing a long Responses generation while deferring control-frame handling. In that situation, the client closes the connection at roughly 40 seconds even though the response stream is making progress. The observed production timing is consistent with this mechanism; no captured close frame establishes it as the cause of every reported disconnect. The source session already has explicit response progress and total-turn deadlines.

## Goals / Non-Goals

**Goals:**

- Keep transport pings so intermediary idle connections remain active.
- Let response-specific deadlines, rather than a shorter generic pong deadline, decide whether source work is stalled.
- Preserve existing source admission, settlement and no-replay boundaries.

**Non-Goals:**

- Replaying a request after `response.create` transmission starts.
- Adding a dashboard setting or changing source selection.
- Removing response first-frame, stream-idle or total-turn timeouts.

## Decisions

Set `ping_timeout=None` on the source WebSocket client while retaining the default 20-second `ping_interval`. This sends keepalive pings and measures no independent pong deadline. A stalled source still reaches the existing first-frame or stream-idle timeout through the receive wait, and the overall request budget remains enforced by the session worker.

The handshake unit test asserts the explicit option. Public-route integration tests use local WebSocket providers that withhold pongs, accelerated transport defaults and observed ping frames to exercise successful streaming/continuation and unchanged timeout/disconnect settlement. The success regression must fail when the finite pong deadline is restored.

## Risks / Trade-offs

- [Risk] A dead peer may remain connected until a response deadline notices it. → [Mitigation] Existing receive deadlines close silent or stalled generations; keepalive pings continue to prevent idle intermediary expiry.
- [Risk] Providers that never answer pings may generate more network traffic before a response deadline. → [Mitigation] The source session still bounds the generation and closes the connection on timeout.

## Migration Plan

Deploy the application change to all HA backends, then monitor `model_source_stream_truncated` and `model_source_timeout` for the CLIProxyAPI source. No migration or source configuration change is required. Rollback is the normal application image rollback.
