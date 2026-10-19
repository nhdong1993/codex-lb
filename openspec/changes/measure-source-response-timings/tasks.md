## 1. Specification

- [x] 1.1 Write proposal, context and the `proxy-runtime-observability` delta. Run `openspec validate measure-source-response-timings --strict`.

## 2. Backend

- [x] 2.1 `SourceDispatch`:
  - `sent_at: float | None`;
  - `first_token_at` / `terminal_at` / pending reasoning state;
  - `observe_relayed_event()`, which uses `_ttft_event_visible_at` and closes the window at the first terminal;
  - `finish()` samples the finalize instant before any await and resolves the row pair (valid upstream pair, else proxy pair, else NULL);
  - update the `sent_at` consumers (`abandon`, `open_with_disconnect_watch`).
- [x] 2.2 `settlement_stream`: observe each relayed event frame after `record_frame` and before `yield`. Parse JSON only while the TTFT window is open.
- [x] 2.3 `SourceWebSocketSession.send()`: observe the event after acquiring `send_lock`.
- [x] 2.4 `_finish_non_stream_source_dispatch`: pass `timings=result.timings` on the `usage_unavailable` branch.
- [x] 2.5 `SourceTimings` docstring: upstream-reported only; the proxy fallback lives in `SourceDispatch`.

## 3. Tests

- [x] 3.1 Unit (`tests/unit/test_source_dispatch.py`, virtual clock):
  - TTFT at the relayed delta and end at the terminal, with the delayed tail excluded;
  - completed-only answer with a stray delta;
  - blank reasoning placeholder; pending reasoning finalized at the terminal;
  - upstream pair wins; absent or malformed metrics fall back;
  - zero-origin clock;
  - abandon before and after send;
  - cancel without a terminal.
- [x] 3.2 Unit (`tests/unit/test_source_websocket_bridge.py`): a send cancelled while queued for `send_lock` sets no TTFT; a completed send does.
- [x] 3.3 Route level:
  - HTTP SSE stream, paced on frames the client received: positive generation interval, a 1.5 s post-terminal tail excluded, positive dashboard TPS, and malformed `metrics` falling back;
  - non-stream latency only;
  - `usage_unavailable` keeps upstream metrics;
  - native WebSocket turns;
  - bridged WebSocket turn with a text delta.
- [x] 3.4 Run the targeted suites serially (no xdist), ruff check/format, `ty`, and the proxy timing-seam guard.

## 4. Ship

- [x] 4.1 Sync the delta into `openspec/specs/proxy-runtime-observability/spec.md` and `context.md`. Run `openspec validate --specs`.
- [ ] 4.2 Archive the change after the operator accepts the result. The specs are already synced (4.1), so archive with `--skip-specs`.
