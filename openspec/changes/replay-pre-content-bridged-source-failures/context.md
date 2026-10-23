# Context: replay pre-content bridged source failures

## Incident (2026-10-23, Asia/Ho_Chi_Minh)

**Request `resp_0b03c746…d98b14`.** Session `01a1687c…`, Codex `codex_exec/0.163.0`, model `http/gpt-6-astra` served by `ch-relay`.

| Attempt (HCM) | Duration | Body sent | Outcome |
|---|---:|---:|---|
| 19:26:41–19:27:01 | 20.5 s | 33,769 B | ch-relay-source-gateway logged `recv() failed (104: Connection reset by peer)` from `127.0.0.1:11502`, after `200` |
| Codex retry 1 | 14.6 s | 33,476 B | reset again |
| Codex retry 2 | 10.7 s | 57,118 B | success |

**Rates.** Over 14 h on this source: 1,620 of about 7,800 WebSocket turns truncated. Sessions with six consecutive truncations then show Codex 0.163's session-level HTTP fallback. Its `responses_retry.rs` resets the retry budget and disables WebSockets for the session. 24 sessions switched that day.

**Earlier packet captures (2026-10-22).** Resets followed `response.created > response.in_progress > response.metadata`, where the metadata was `openai_chatgpt_moderation_metadata`. About 2 s later the relay reset the downstream connection, after it had sent a new upstream request.

**Relay A/B, from 20:29 HCM.** `CH_TRANSIENT_RETRIES=0` on the existing instance, same image. Pre-content resets turned into clean failure terminals carrying `upstream_error_code=server_is_overloaded`, and each coincided with a relay log line `ERROR uncaught exception (kept serving): TypeError: h is not a function`. Codex's next attempt usually succeeded.

## Decisions

- **Hold only the lifecycle prefix.** It counts as prefix only while it carries no output:
  - `response.created`, `response.in_progress` and `response.queued` with `response.output` absent or empty;
  - `response.metadata` with only `type`, `metadata`, `headers`, `response_id` and `sequence_number`. This matches Codex 0.163's `metadata.openai_chatgpt_moderation_metadata`, `openai_verification_recommendation` and `type: safety_buffering` shapes.

  Any other event first flushes the held events in source order, then is relayed as before. Nothing held is published to source ownership or handed to the client. That makes the withheld attempt invisible: the client never sees two `response.created` events or two response ids.
- **Replay at most once per client turn.** An earlier review debate noted that one extra attempt cannot reclaim the 10–20 s an attempt already spent. It does keep the client's WebSocket retry budget from driving the session into HTTP fallback. Only the first attempt of a turn holds the prefix. The replacement relays immediately, as today.
- **Two eligible failures, both pre-content:**
  1. a body reset, or EOF without a terminal (`model_source_stream_truncated`);
  2. a failure terminal whose sanitized upstream code is `server_is_overloaded`, which Codex itself treats as transient.

  Other failure codes are not replayed. That includes `internal_error`, which ch-relay's `reqcache` replays deterministically, and timeouts, invalid events, ownership failures, client departure and drain.
- **Same source, revision, model and reconstructed body.** The replacement is prepared through the normal turn preparation, bound to the session identity, with the original `received_at`. It therefore rechecks policy, takes a fresh admission claim and reservation, and is limited by the original deadline. It never moves to another source.
- **Accounting stays per attempt.** The failed attempt is finalized before the replacement is prepared: its response is closed, its reservation released, and its row written. If preparing the replacement fails, it leaves no row, and the client receives the original failure as a WebSocket `error` event. A refused reservation for the replacement behaves like any refused turn.
- **Payload-free trace.** `failure_detail` on non-success bridged rows, for example `source_bridge events=created,in_progress,metadata handed_off=none replay=eligible`. Event kinds come from a fixed vocabulary. Consecutive repeats are collapsed, at most eight kinds are kept, and `+` marks more. No ids, metadata values, text or messages are stored.

## Residual risk

- Replay is not exactly-once upstream execution. The failed attempt may already have spent quota upstream, and a relay may keep running orphan work.
- "Same source" does not mean the same ChatGPT account behind a relay.
- A held-back `response.metadata` (safety-buffering hint) reaches the client only together with the first content of the attempt that succeeds.
- `latency_response_created`-style timings for bridged rows are stamped at the moment the events are handed off.

## Example

Source SSE, attempt 1: `response.created`, `response.in_progress`, `response.metadata`, then the connection resets.

- Row 1: `status=error`, `error_code=model_source_stream_truncated`, `failure_detail=source_bridge events=created,in_progress,metadata handed_off=none replay=eligible`. Reservation released.
- Log line: `source_bridge_replay request_id=<row 1> reason=model_source_stream_truncated`.

Attempt 2: the same body to the same source, which streams `response.created … response.completed`.

- The client receives only attempt 2's events.
- Row 2: `status=success`. Reservation settled.

## Operations

- **Rollback of the relay A/B:** remove `CH_TRANSIENT_RETRIES` from `/home/dong01/ch-relay-docker/compose.yaml` (backup `compose.yaml.bak-20261023-transient-ab`), then run `sudo docker compose up -d --no-build --no-deps relay`.
- **Measure:** compare the per-10-minute `model_source_stream_truncated`, `model_source_response_failed` and success counts for the source, and query `failure_detail LIKE 'source_bridge %'`.
