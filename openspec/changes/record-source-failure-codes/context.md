# Context: record source failure codes

## Incident (2026-10-20, Asia/Ho_Chi_Minh)

- Session `01a14d48…` on `ch-relay/gpt-6-astra` sent a 221,951-token compaction (969,081-byte body) at 18:11 and again at 22:31. Over HTTP, ch-relay logged `autocut seg cap reached segs=24` and synthesized `response.incomplete` with reason `upstream_eof`. At 23:51 the same body went over the WebSocket bridge. ch-relay answered with a 169-byte failure frame after about 2 s, and Codex retries got a 163-byte `reqcache` replay.
- Session `01a15954…` (`http/gpt-6-astra`, later `http/gpt-6-sol`) failed every turn from 20:35 onward the same way, with 7–9 MB bodies.
- Every row read `error_code = model_source_response_failed`, `upstream_status_code = 200` and `upstream_error_code = NULL`. Finding out what the source said took a tcpdump of production traffic.

## Decisions

- **Code only, never the message.** The bridge and the native session redact provider messages because they can carry credentials or private URLs (see `model-source-websocket`). A code is an identifier, and a strict pattern (`^[a-z0-9][a-z0-9_.:-]{0,63}$` after trim+lowercase) stops free text from getting in through the code field.
- **Existing column.** `upstream_error_code` already carries upstream codes for subscription rows, and the dashboard and telemetry already read it. Telemetry maps any code outside `_SAFE_UPSTREAM_ERROR_CODES` to `other`, so source-specific codes never leave the instance.
- **Parser-level capture.** `SourceStreamUsageParser._observe_responses_event` is the one observer shared by the HTTP SSE stream, the native source WebSocket session and the bridge. Capturing there covers all three without touching their sanitizing relays.
- **First failure wins.** A relay may send `error` and then a success-shaped `response.incomplete`, which ch-relay does after autocut gives up. The first failure explains the attempt, and later frames must not overwrite it.
- **Non-success rows only.** A `success` row never shows a failure code, even when a failure frame was observed and later superseded.

## Example

Source SSE over the bridge:

```
event: error
data: {"type":"error","error":{"type":"server_error","code":"upstream_eof","message":"token at https://private.example"}}
```

Client: `{"type":"error","status":502,"error":{"code":"model_source_response_failed","message":"Model source failed the response",...}}` (unchanged).

Row: `status=error`, `error_code=model_source_response_failed`, `upstream_error_code=upstream_eof`. The message is stored nowhere.

## Failure modes

- A source that sends no code and no type, or only unsafe values, leaves `upstream_error_code` NULL, which is the current behaviour.
- Source HTTP errors that arrive before the stream are out of scope; they keep the existing forwarding-error path.
