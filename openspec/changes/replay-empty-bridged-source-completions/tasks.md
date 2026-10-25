## 1. Specification

- [x] 1.1 Write the proposal, the context and the `model-source-websocket` delta. Run `npx --yes @fission-ai/openspec@1.11.0 validate replay-empty-bridged-source-completions --strict`.

## 2. Tests (red first)

- [x] 2.1 Route: a reasoning-then-empty-message completion is replayed invisibly. Assert:
  - the client receives only the replacement's events, with one `response.created`;
  - the source receives two identical bodies;
  - the rows are `(success, model_source_empty_completion)` with usage, then `(success, None)`;
  - both reservations are finalized;
  - no admission is left in flight;
  - the next turn continues from the replacement.
- [x] 2.2 Route: reasoning followed by visible text, and reasoning followed by a function call, are delivered in source order with no replay.
- [x] 2.3 Route: `response.incomplete` after only reasoning is delivered unchanged. A `response.completed` that carries its answer only in the envelope is delivered, not replayed. A replacement that also completes empty is delivered, with exactly two requests.
- [x] 2.4 Route: a replacement that cannot be admitted gives the client the error `model_source_empty_completion`, with one marked success row. A reset after a reasoning item is replayed. An outsized held reasoning item is delivered and not replayed.

## 3. Backend

- [x] 3.1 `_bridge_held_event()` classifies the lifecycle prefix plus output-free events. `_relay_http` uses it for holding.
- [x] 3.2 `_relay_http` finalizes an empty completion as a billed success with `model_source_empty_completion`, then raises it as replay-eligible. The existing `_worker` and `_bridged_replacement` replay and log it.

## 4. Verify and ship

- [x] 4.1 Run the bridge and source-WebSocket suites serially, `ruff check`, `ruff format --check` and `ty`.
- [ ] 4.2 Run `/review-impl`. Sync the delta into the main spec and `context.md`. Run `npx --yes @fission-ai/openspec@1.11.0 validate --specs`.
- [ ] 4.3 Deploy through the HA rollout, only on the operator's request. Confirm `model_source_empty_completion` rows and replays in production.
- [ ] 4.4 Archive after the operator accepts the result.
