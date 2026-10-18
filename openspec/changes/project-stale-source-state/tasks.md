## 1. Specification

- [x] 1.1 Write proposal, context and the `model-source-routing` and `model-source-websocket` deltas; run `openspec validate project-stale-source-state --strict`.

## 2. Backend

- [x] 2.1 In `_resolve_source_response_candidates`, after the existing per-candidate rejection, classify the candidate's union keys (foreign / stale-self). When only stale-self keys exist, load owners (active and history) for the raw `item_keys` of every input item. Lookup failure keeps the 502. The boundary is the last item with a `(X, earlier revision)` raw key. Reject when there is no boundary, when the prefix has an `item_reference`, or when the projection leaves no input. Otherwise project the prefix with `project_responses_input_for_account_neutral_fresh_replay`.
- [x] 2.2 Build the projected original view (projected input, replayed tool-call namespaces stripped, client anchors kept) and the projected effective view (normal shaping for `X`). Require the union of their keys to be a subset of the looked-up keys, then re-check: owners all `(X, current revision)`, no effective-only unknown keys, no unknown keys in a pool. On success, store the projected effective body, its exact keys as `request_keys[X]` (the union is for validation only), and the projected input. Mark the candidate non-portable and log `source_stale_state_projected` with counts.
- [x] 2.3 Carry projected inputs on `_SourceResponseCandidates`. HTTP dispatch in `_balanced_source_responses_response` sends the projected input. The exact forwarded-key guard and both recorders stay unchanged. WebSocket keeps using `resolved.payloads` and `resolved.request_keys`, with the bound-socket revision check unchanged.

## 3. Tests

- [x] 3.1 HTTP regression on `/v1/responses` and `/backend-api/codex/responses` (stream and non-stream): change `upstream_model` and, separately, the token, then resend the full transcript. Expect 200 with the stale prefix projected and the call/result pair kept. Cover a tool-only continuation (no assistant message after the stale call: old reasoning and `fc_` id removed) and a complete namespaced pair. A later turn keeps the post-change suffix reasoning and ids.
- [x] 3.2 Guards still return 409 with no dispatch: stale `previous_response_id`; an override that clears a stale anchor; stale compaction item; `item_reference` in the prefix; reasoning-only input (empty projection); state owned by another source; unresolved stale `call_id`.
- [x] 3.2b HTTP: stale inline state is projected while a source override removes a current-revision-owned `prompt` from the effective body. Expect 200, the guard passes, and the recorded input keys equal the forwarded body's keys (no stale key recorded under the new revision).
- [x] 3.3 Pool: stale state on pool member A is projected and sent only to A. A retryable failure does not fail over.
- [x] 3.4 WebSocket: after a mapping change, the old bound socket gets `websocket_reconnect_required` with no frame forwarded. A new connection's full-transcript `response.create` reaches the source with the projected input.
- [ ] 3.5 Re-run the existing replaced-credential and ownership suites; adjust only expectations that the new requirement changes and document each.
- [x] 3.6 Run targeted pytest (serial), ruff and `openspec validate --specs`.
