## 1. Specification

- [x] 1.1 Write the proposal, context, and the `model-source-websocket` and `responses-api-compat` deltas; run `openspec validate route-websocket-compaction-through-sources --strict`.

## 2. Regression tests (fail before the fix)

- [x] 2.1 Bridged first-turn compaction on both route families: the HTTP-only source receives one streaming request whose input ends with the trigger, the client receives the compaction item and `response.completed`, no subscription path is used, and the request log records `websocket`/`openai_compatible_http`/`compaction`.
- [x] 2.2 Bound bridged compaction: after a completed turn, a compaction continuing that response with only the trigger reaches the same source with the reconstructed input and no `websocket_reconnect_required`.
- [x] 2.3 Native source session compaction: the native provider receives the compaction create and the turn completes.
- [x] 2.4 Subscription-anchored source-only compaction: the test that pinned the subscription path now covers the remaining `input_file` structural exclusion, and a new test expects 503 `model_source_requires_http_transport`, no source or subscription dispatch and no reservation.
- [x] 2.5 Disabled-source compaction over WebSocket: 503 `model_source_disabled`, no subscription dispatch and no reservation.
- [x] 2.6 Continuation after a bridged compaction (review round 1; operator chose option A on 2026-10-21): referencing the compaction response gets the route's continuity error with no source request or reservation, and a full resend of the compacted history succeeds after reconnect.

## 3. Implementation

- [x] 3.1 `_prepare_source_websocket_turn`: evaluate structural exclusion with `exclude_compaction=False`; pass `request_kind` to `SourceDispatch`.
- [x] 3.2 Update the `responses_source_route_excluded` docstring.
- [x] 3.3 `SourceWebSocketSession._remember`: do not store continuation state for a completed compaction turn.

## 4. Documentation and verification

- [x] 4.1 Update `docs/model-source-websocket.md` and `openspec/specs/model-source-websocket/context.md`.
- [x] 4.2 Run the new and affected suites (source WebSocket, bridge, policy review, WebSocket model-source guard, source compaction, compact), ruff check/format and the type checker on touched files, and strict OpenSpec validation. Results and the pre-existing/flaky failures are recorded in [verification.md](verification.md).
- [x] 4.3 Gate: implementation cross-review returns APPROVE with accepted findings fixed and re-verified (APPROVE, session review-impl-20261021-001 round 2, 2026-10-21; 1 plan-gap finding resolved by operator option A under 2.6/3.3).

## 5. Completion gates

- [x] 5.1 Sync the deltas into the main specs and run `openspec validate --specs` (67 passed).
- [ ] 5.2 Commit, push and deploy only with explicit operator approval; after deployment, verify a real Codex auto-compaction on a `ch-relay/*` model is source-routed in request logs.
- [ ] 5.3 Archive the change only after production verification.
