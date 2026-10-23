## 1. Specification

- [x] 1.1 Write the proposal, context, and `model-source-websocket` / `proxy-runtime-observability` deltas. Run `openspec validate replay-pre-content-bridged-source-failures --strict`.

## 2. Tests (red first)

- [x] 2.1 Route (WebSocket→HTTP bridge): a reset after the lifecycle prefix is replayed invisibly. Assert one `response.created` for the client, two identical bodies, error then success rows, released then finalized reservations, the trace on the error row, and no admission left in flight.
- [x] 2.2 Route: an EOF without a terminal and a pre-content `server_is_overloaded` failure are replayed.
- [x] 2.3 Route: no replay after content, for `server_error`, or a second time. Check the traces and the delivered events.
- [x] 2.4 Route: when the replacement cannot be admitted or its effective body changed, the client gets the original `model_source_stream_truncated` and there is one row. Also covered: prefix-flush terminal handoff, the handoff trace when a send fails, a trace on rows that fail before the relay starts, and the bounded prefix.

## 3. Backend

- [x] 3.1 `SourceDispatch.failure_detail` is passed by `write_row()` for non-success rows.
- [x] 3.2 `_relay_http` holds the lifecycle prefix, keeps the trace, and marks replay eligibility.
- [x] 3.3 `_worker` replays an eligible first attempt once through bound preparation, keeping the original deadline. It logs `source_bridge_replay`.

## 4. Verify and ship

- [x] 4.1 Run the targeted suites serially, `ruff check` / `ruff format --check`, and `ty`.
- [x] 4.2 Run `/review-impl`, then sync the deltas into the main specs and `context.md`. Run `openspec validate --specs`.
- [ ] 4.3 Deploy. Confirm `source_bridge` traces and replays in production rows. Compare against the relay A/B baseline.
- [ ] 4.4 Archive after the operator accepts the result.
