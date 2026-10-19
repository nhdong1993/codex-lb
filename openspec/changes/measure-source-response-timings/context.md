# Context: proxy-measured timings for model-source Responses requests

## Problem (2026-10-19)

The operator asked why model-source rows had no TTFT or TPS in the dashboard request log. A read-only production aggregate over the previous 7 days showed:

- about 14,900 source rows (HTTP 10,795; native WebSocket 3,726; WebSocket→HTTP bridge 406; compaction 14);
- `latency_ms` and `latency_first_token_ms` NULL on every one of them;
- output tokens and reasoning tokens present on about 95% of them.

The only timing source was an upstream vLLM-style `metrics` object (`_timings_from_payload`). The production sources do not send one, and the archived design `2026-08-13-source-upstream-timing-metrics` deliberately left proxy-side measurement out of scope.

## Decisions

- **Where it is measured.** `SourceDispatch` measures the timings, because every Responses source attempt has exactly one `SourceDispatch` and ends in `finish()`. Chat-completions and audio-transcription routes have no dispatch owner and carried no production traffic in the sample, so they keep the metrics-only rule.
- **Same TTFT definition as subscription traffic.** `_ttft_event_visible_at` is reused. Text, refusal and reasoning deltas, non-empty tool-argument deltas, non-blank reasoning summaries and qualifying tool-call items count. `response.created`, `response.in_progress` and keepalives do not.
- **Stamped at handoff, not at parse.**
  - On HTTP the stamp is taken in `settlement_stream`, after continuity publication and right before the frame is yielded to the transport. It therefore includes the pin write and the public wrapper's parking, which the client really waits for.
  - On WebSocket the stamp is taken inside `SourceWebSocketSession.send()` after acquiring the send lock. A frame cancelled while queued for the lock never counts.
  - Stamping inside the stream parser was rejected: it runs below the public wrapper and before the pin hook.
- **Ends at the relayed terminal.**
  - Many sources keep the HTTP body open after `response.completed` (`[DONE]`, keepalives). The bridge also closes the HTTP response before finishing the turn. Ending at `finish()` would therefore stretch `latency_ms` and depress TPS differently per transport.
  - When no terminal was relayed (cancel, truncation, error before a terminal), the end is one clock sample at `finish()` entry, taken before any settlement await.
  - The terminal also closes the TTFT window, so a stray delta after a completed-only answer cannot produce TTFT > latency.
- **Upstream metrics first.** A valid upstream pair is more precise (it excludes network time) and is kept unchanged. Absent and malformed metrics both use the proxy fallback. The parser already rejects invalid pairs, so no presence flag is needed. Pairs are never mixed.
- **`sent_at` is `float | None`.** Zero is a valid injected monotonic value (the virtual clock starts at 0.0), so "not sent" needs its own state.

## Rows that stay blank (by design)

- **TTFT NULL:**
  - non-stream JSON responses and compaction (the client sees no tokens before the body);
  - completed-only answers whose content is only in the terminal envelope;
  - streams that end before any visible frame;
  - attempts never sent.
- **TPS blank in the dashboard** (it requires TTFT, `latency_ms > TTFT`, and positive non-reasoning output tokens):
  - every TTFT-NULL row;
  - rows with missing usage;
  - reasoning-only output;
  - a zero-millisecond generation interval.

## Measurement provenance and dashboards

- Proxy-measured source values include network time to the source and the source's own queueing. Upstream-reported vLLM values do not. Both live in the same columns, so a source's numbers can shift if it starts or stops sending `metrics`.
- Because TTFT is stamped at handoff, it includes the continuity-ownership writes that run before each frame is handed off (`SourceOwnershipRecorder.record_frame`). The client really waits for them. In a loaded test environment on SQLite, a single write reached 1–2 s. On production Postgres they should be milliseconds, and a TTFT spike that is not matched by the source's own speed points there.
- Native WebSocket attempts start after the upstream socket is connected, because `sent_at` is taken right before `response.create` is sent. HTTP and bridged attempts start before the HTTP open, so their first token includes connect and header wait.
- The Reports daily medians (TTFT, TPS) filter only on timing validity. After deploy they include source rows, so the charts can move with no backend getting faster or slower. Filtering by account restores an account-only view.
- In the Grafana TTFT dashboard, the 24-hour breakdown groups by upstream transport (`openai_compatible_http` / `openai_compatible_websocket` for sources). The prewarm and session-gap panels do not group by transport, so source rows enter those cohorts too.

## Example

A Codex turn sent over HTTP to an OpenAI-compatible relay:

| t (ms after send) | Relayed to the client |
|---|---|
| 0 | the proxy sends the request |
| 120 | `response.created` |
| 300 | first `response.output_text.delta` |
| 1000 | `response.completed` (usage: 21 output tokens, 0 reasoning) |
| 3000 | `[DONE]`, then the body closes |

The row records `latency_first_token_ms = 300` and `latency_ms = 1000`. The dashboard shows TTFT `300ms` and TPS `21 / 0.7 = 30.0`. Ending at body close would have shown `21 / 2.7 = 7.8`.

## Failure modes

- Clock reads use the injected owner or session clock. The proxy timing-seam guard bans raw `time.monotonic()` in these modules.
- Timing never changes status, settlement, or delivery. It only writes two nullable columns on the row the dispatch already writes.
