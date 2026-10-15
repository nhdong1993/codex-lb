## 1. Contract

- [x] 1.1 Write the `responses-api-compat` and `model-source-websocket` delta specs for source-only models with recorded subscription continuity on the direct Responses WebSocket transport.

## 2. Implementation

- [x] 2.1 Add the shared source-only predicate `responses_model_is_source_only` in `app/modules/model_sources/selection.py`.
  - It is true when an enabled or disabled Responses-capable source claims the model under the ordinary selection rules, and no candidate is in the subscription model registry. Candidates are the raw client model (or the API key's enforced model) and the normalized model.
  - It checks the registry first, so anchored subscription turns skip the database.
  - It reuses `select_responses_model_source` instead of a second candidate rule.
  - Unlike the fail-open `responses_model_is_source_owned`, lookup errors fail closed through the preflight.
- [x] 2.2 In `_prepare_source_websocket_turn` (`app/modules/proxy/api.py`), apply the predicate in both the turn-state owner branch and the recorded previous-response owner branch.
  - A source-only turn is refused with 503 `model_source_requires_http_transport` (`server_error`) instead of returning to subscription routing.
  - The refusal is raised before admission, reservation and request-log preparation.
  - It applies on first turns and on subscription-bound or source-bound sockets.
  - Required-capability routing and structural exclusions still run ahead of it.
- [x] 2.3 Mixin connect and reuse source guards (`app/modules/proxy/_service/websocket/mixin.py`): verified reachable for a source-only model only through sanctioned precedence (capability routing, structural exclusions). Left unchanged.
- [x] 2.4 Confirm that HTTP Responses routing and the registry-slug / source-scoped owner precedence are unchanged.

## 3. Regression coverage (public WebSocket route, both route families)

- [x] 3.1 Incident shape, on the same socket: a subscription `generate:false` warmup, then a source-only `response.create` chained to it with `previous_response_id`. Also a recorded owner on a first turn.
  - Expected: 503 `server_error` `model_source_requires_http_transport`, no subscription upstream frame and no source dispatch.
  - The socket keeps serving the anchored account afterwards.
- [x] 3.2 A recorded subscription owner of a first turn with a native-WebSocket-capable source gets the same refusal before source admission.
- [x] 3.3 A client-supplied turn-state alias owned by a subscription account with a source-only model gets the same refusal.
- [x] 3.4 A source-bound socket with a subscription-owned `previous_response_id` gets 503 `model_source_requires_http_transport` instead of 409 `websocket_reconnect_required`.
- [x] 3.5 Registry-slug precedence: a source-scoped key routing a registry slug to its source, with a previous-response or turn-state anchor, stays on the owner-bound subscription path.
- [x] 3.6 A disabled source-only model with a recorded owner gets `model_source_requires_http_transport`.
- [x] 3.7 Structural exclusion: a terminal `compaction_trigger` with a recorded owner stays on subscription without `model_source_requires_http_transport`.
- [x] 3.8 Run only the affected test files, sequentially (this host is the production Docker host, so do not run the full suite), plus Ruff and `ty` on the touched files.

## 4. Verification and archive

- [x] 4.1 `npx --yes @fission-ai/openspec@1.11.0 validate route-source-only-models-off-subscription-owner-pin --strict`
- [x] 4.2 `npx --yes @fission-ai/openspec@1.11.0 validate --specs`
- [x] 4.3 On archive:
  - Sync the deltas into `openspec/specs/responses-api-compat/spec.md` and `openspec/specs/model-source-websocket/spec.md`.
  - Move stable context into `openspec/specs/responses-api-compat/context.md`.
  - The still-active `add-model-source-websocket` change carries deltas for all three requirements modified here: "Previous-response source routing follows proven ownership" and "A disabled model source refuses its models instead of falling through" (`responses-api-compat`), and "Source WebSocket routes retain source authorization and payload semantics" (`model-source-websocket`). Its archive-time spec sync must not overwrite this change's text. Archive it with spec updates skipped, or re-apply this change afterwards.
