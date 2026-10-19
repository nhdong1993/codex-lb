## 1. Specification

- [x] 1.1 Write proposal, design, and the `model-source-websocket`, `responses-api-compat` and `api-key-dashboard` deltas; run `openspec validate bridge-source-websocket-over-http --strict`.
- [x] 1.2 Gate: the plan cross-review (`review-plan`) returns APPROVE before any code change (APPROVE, session review-plan-20261018-003, 2026-10-18; 8 findings fixed across sessions 001–002).

## 2. Discovery and handshake

- [x] 2.1 `catalog.source_websocket_models`: count enabled streaming models of enabled Responses sources as WebSocket-capable regardless of the native flag.
- [x] 2.2 `_websocket_upstream_transport_denial`: drop the native requirement from the subscription-outage source exemption.

## 3. Session and routing

- [x] 3.1 Add `upstream` to `SourceSocketIdentity` and `SourceWebSocketTurn`, plus `client_input` on the turn; select the mode in `_prepare_source_websocket_turn` (native preferred, bound mode sticky); set `upstream_transport` per mode; keep `model_source_requires_http_transport` for an unbound empty streaming pool; make the disabled-source branch always `model_source_disabled`; raise the continuity error for a client `previous_response_id` on an `http` turn before admission.
- [x] 3.2 Add the injected `open_http` opener in `api.py` (`stream_source_responses` + `_iter_source_sse_event_blocks`, with error mapping) and pass it to the session.
- [x] 3.3 Refactor the worker open loop: move the failover body into `_retry_elsewhere` with an unbound-session guard; for bridged turns, return the original forwarding error when re-preparation finds no replacement (`model_source_busy`); open HTTP per bridged turn under the turn deadline and classify that deadline's `TimeoutError` as 504 `model_source_timeout` (finish once, no failover or replay); set `identity` after the first successful open.
- [x] 3.4 Extract `_relay_event` from `_relay`; add `_relay_http` with SSE filtering, output-item collection, transcript update, close-before-finish, and truncation on EOF.
- [x] 3.5 Add `_BridgeTranscript` and `_expand_continuation` (exact-id match only, string input normalization, size bound); call it for queued bridged turns before `prepare`, leaving unmatched ids to `prepare`'s anchor checks and continuity error.
- [x] 3.6 Bridged warmup: bind the session identity, store the transcript, synthesize `response.created`/`response.completed`, and `discard()` the dispatch. Add `SourceDispatch.discard()`, and route bridged warmups in `_finish_interrupted()` to `discard()` so every exit (including before the worker starts) releases admission once without a row or metric.
- [x] 3.7 Make `_close_upstream()` close the active bridged HTTP stream.

## 4. Tests

- [x] 4.1 Transcript expansion is covered through the public route (exact-id match, unknown/stale id, failed response, string input, size bound) in `test_model_source_websocket_http_bridge.py`; unit test for `SourceDispatch.discard()` in `tests/unit/test_source_dispatch.py`.
- [x] 4.2 Integration (both public routes): source-only HTTP-only key accepted; first turn POSTs a stream request without `generate`, `type` or `previous_response_id`; events reach the client in order with the public model; request log `websocket`/`openai_compatible_http`; reservation settled.
- [x] 4.3 Integration: a tool-call continuation reconstructs `input + output items + delta`; warmup sends nothing upstream, writes no request log, and its immediate continuation on the same socket succeeds with the warmup input; an unknown or stale `previous_response_id` returns the route's continuity error without a POST or reservation; a disconnect or drain after warmup preparation but before execution releases admission once with no reservation, POST, request-log row or dispatch metric.
- [x] 4.4 Integration: source 429/5xx before the stream (error envelope, reservation released once); pooled portable first-turn failover to a healthy source; single-source 429 and an exhausted two-source pool return the last source error, not `model_source_busy`; turn deadline expiring during the HTTP open with the lifecycle watcher held off returns 504 `model_source_timeout`, logs a timeout, closes the request and releases admission; in-stream `response.failed` (sanitized, session continues); mid-stream disconnect and client departure (HTTP response closed, admission released, cancellation accounting).
- [x] 4.5 Integration: mixed key bridges an HTTP-only streaming source model instead of `model_source_requires_http_transport`; mixed key with a non-streaming source model still gets `model_source_requires_http_transport` after upgrade; a subscription-anchored source-only turn keeps `model_source_requires_http_transport`; native-capable pools still use native WebSocket.
- [x] 4.6 Catalog and installer: streaming HTTP-only source models prefer WebSocket and enable the source-only installer flag; non-streaming pools keep HTTP and the 426 handshake.
- [x] 4.7 Update existing tests that pinned 426 or `model_source_requires_http_transport` for HTTP-only streaming sources.

## 5. Documentation and verification

- [x] 5.1 Update `docs/model-source-websocket.md` and the change context (bridge behavior, transcript scope, warmups, kill switch, installer re-export).
- [x] 5.2 Run targeted pytest serially (`-n` ≤ 2), ruff check/format, the type checker on touched files, and `openspec validate --strict`.
- [x] 5.3 Local real-client acceptance with Codex CLI 0.163 against an isolated dev instance and an HTTP/SSE stub source. Capture the client leg through a logging relay (accepted upgrade, warmup, incremental create with `previous_response_id`, its completion, zero client HTTP Responses POSTs) and the source leg (reconstructed bodies). Record the redacted evidence in `verification.md`.

## 6. Review, sync and completion gates

- [x] 6.1 Gate: the implementation cross-review (`review-impl`) returns APPROVE with every accepted finding fixed and re-verified. (APPROVE, session review-impl-20261018-001 round 3, 2026-10-18; 3 findings fixed: full-request size bound made exact, shared HTTP close latch, native-flag rollout guidance.)
- [x] 6.2 Sync the deltas into `openspec/specs/{model-source-websocket,responses-api-compat,api-key-dashboard}/spec.md` and the capability `context.md`; run `openspec validate --specs` and `openspec validate bridge-source-websocket-over-http --strict`.
- [ ] 6.3 Archive the change only when it ships (after the operator approves commit/merge/deploy and production verification); commit, push and deploy need explicit operator approval.
