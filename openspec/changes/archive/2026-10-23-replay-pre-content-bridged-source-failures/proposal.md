## Why

On 2026-10-23 about 20% of Codex WebSocket turns bridged to the `ch-relay` source (`http/gpt-6-astra`) failed with `model_source_stream_truncated` (15–30% per hour). Example: `resp_0b03c746c05b706e016adb5281ed7c819180e2507231d98b14` at 19:26:41 HCM.

- **Fault boundary.** The relay reset the HTTP response after `200` and about 33.7 KB of body. In each case that was only the lifecycle prefix: `response.created`, `response.in_progress`, `response.metadata`. codex-lb reported the reset correctly.
- **Relay behaviour.** A production A/B on the relay (`CH_TRANSIENT_RETRIES=0`, from 20:29 HCM) points at the underlying upstream failure: some requests end with an upstream `server_is_overloaded` failure.
  - With the relay's internal retry enabled, that failure is followed by a downstream reset.
  - With the retry disabled, the reset becomes a clean failure terminal (`upstream_error_code=server_is_overloaded`), and the relay logs `uncaught exception … TypeError: h is not a function`.
  - Gateway byte counts are consistent with no output before the failure. The trace added here is how that will be confirmed.
- **Client cost.** Codex retries either shape. Each failed attempt still costs the client 10–20 s. After six WebSocket failures in a row, Codex 0.163 moves the whole session to HTTP fallback, which is less reliable here. On 2026-10-23, 24 sessions switched, and of their 1,238 later HTTP rows only 96 succeeded cleanly.
- **Diagnosis gap.** The request log could not show which events had reached the client before a failure. That made it impossible to tell whether a retry would have been safe.

## What Changes

- **Hold the prefix.** A bridged HTTP/SSE turn holds back the lifecycle prefix until the first other event arrives. The prefix is `response.created`, `response.in_progress` and `response.queued` with no output, and `response.metadata` with only metadata fields.
- **Replay once.** A failure while the prefix is still held back is replayed once, to the same source and revision, with the same reconstructed body, inside the original turn deadline. Two failures qualify:
  - the source body resets or ends without a terminal event;
  - a failure terminal whose sanitized upstream code is `server_is_overloaded`.
- **Accounting.** The failed attempt keeps its own request log and its reservation release. The replacement takes a fresh admission claim and a fresh reservation. The client sees only the replacement's events.
- **No replay otherwise.** There is no replay after any event was handed to the client, for any other failure code or error class, for native source sessions, for warmups, or while draining. A replacement that cannot be prepared returns the original failure.
- **Stream trace.** Non-success request-log rows of bridged turns store a payload-free stream trace in `failure_detail`: event kinds observed, what was handed off, and replay eligibility. A structured log line records each replay.
- No schema, migration, setting, API or frontend change.

## Capabilities

### Modified Capabilities

- `model-source-websocket`: the no-replay rule gains the single bridged pre-content exception. A new requirement, "Bridged turns replay one pre-content source failure", is added.
- `proxy-runtime-observability`: a new requirement, "Bridged source failures record a payload-free stream trace", is added.

## Impact

- `app/modules/proxy/source_websocket.py`: prefix holding and the trace in `_relay_http`, and the same-source replay in `_worker`.
- `app/modules/proxy/source_dispatch.py`: a `failure_detail` field passed by `write_row()` for non-success rows.
- Tests: `tests/integration/test_model_source_websocket_http_bridge.py`.

## Non-goals

- Replaying after content, replaying on native source WebSockets or the plain HTTP route, and cross-source replay.
- Fixing the relay itself. The relay A/B and the vendor report are operational follow-ups, recorded in `context.md`.
- The HTTP-route `model_source_idle_timeout` misclassification seen in the same incident.
