## Why

The dashboard request log, the key dashboard and the Reports trends show TTFT and TPS for subscription-backed requests, but every model-source row is blank. On 2026-10-19 the 7-day production sample had about 14,900 source rows, and none of them carried `latency_ms` or `latency_first_token_ms`.

Source timings come only from a vLLM-style upstream `metrics` object. None of the production sources (relays and OpenAI-compatible gateways) send one, and the current requirement says such rows MUST stay NULL. Operators therefore cannot compare source speed with account speed or see when a source slows down.

## What Changes

- For source-routed **Responses** requests (HTTP stream, non-stream, compaction, native WebSocket, and the WebSocket→HTTP bridge), the proxy measures timing itself when the source reports no valid upstream timing pair:
  - **Start:** when the request is sent to the source.
  - **TTFT:** when the first client-visible token is handed to the client, using the same classifier as subscription-backed requests.
  - **End:** when the first terminal event is handed to the client, or when the attempt finalizes if no terminal was relayed.
- A valid upstream `metrics` pair still wins unchanged. Absent or malformed metrics fall back to the proxy measurement on these paths.
- Non-stream responses and compaction record total latency only.
- Fix: the non-stream `usage_unavailable` error row now keeps valid upstream timings like every other non-stream outcome.
- Chat-completions and audio-transcription routes keep their metrics-only behavior.
- No schema, migration, setting, API, or frontend change.

## Capabilities

### Modified Capabilities

- `proxy-runtime-observability`:
  - narrow "Source-routed requests report upstream-measured generation timings" so the NULL-when-absent rule applies to chat-completions and audio transcription;
  - add "Source-routed Responses requests fall back to proxy-measured timings".

## Impact

- Backend:
  - `app/modules/proxy/source_dispatch.py` (`SourceDispatch` timing state, `settlement_stream` observation, `finish()`/`write_row()` resolution, `sent_at` typed `float | None`);
  - `app/modules/proxy/source_websocket.py` (`send()` observation under the send lock);
  - `app/modules/proxy/api.py` (`usage_unavailable` timings);
  - `app/modules/model_sources/forwarding.py` (`SourceTimings` docstring).
- Data: new source rows populate the existing nullable `request_logs.latency_ms` / `latency_first_token_ms` columns. Historical rows stay NULL, because there is nothing to backfill.
- Reports daily medians and the Grafana TTFT dashboard start including source rows. Queries are unchanged; see `context.md`.

## Non-goals

- Chat-completions and audio-transcription direct routes.
- Always preferring proxy timing over valid upstream metrics.
- Backfilling historical rows, source TTFT Prometheus phase histograms, `latency_queue_ms` for sources.
- Changing Reports, Grafana, or dashboard queries and rendering.
