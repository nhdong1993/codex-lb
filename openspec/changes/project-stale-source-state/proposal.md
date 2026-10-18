## Why

Changing a source model's upstream mapping, endpoint or token changes its ownership fingerprint. After that, every existing Codex conversation on that model fails each turn with `409 model_source_owner_unavailable`, because Codex resends the earlier encrypted reasoning and upstream item ids that were recorded under the old fingerprint. Codex cannot strip that state itself, so the conversation is permanently broken. On 2026-10-18 this happened twice to `ch/gpt-6-astra` after the operator edited its `upstream_model` (see `context.md`).

## What Changes

- When a candidate source's only ownership conflict is its own earlier revision, the proxy projects the input prefix that ends at the last item carrying that stale state. It drops reasoning items and completed web/tool-search calls, and strips item ids. It then dispatches the request to the same source.
- Stale anchors (`previous_response_id`, `conversation`, `prompt`, containers, vector stores), stale compaction content, unresolved stale call ids, `item_reference` items and state owned by another source keep the existing 409.
- A projected dispatch never fails over to another source and never re-records the stale references.
- On WebSocket, recovery happens after the client reconnects. A socket bound to the old revision still gets `websocket_reconnect_required`.
- No setting, migration or API change.

## Capabilities

### Modified Capabilities

- `model-source-routing`: refine "Source response continuity preserves credential ownership" for same-source reconfiguration.
- `model-source-websocket`: allow the same projection on a fresh or reconnected source session. A socket bound to the earlier revision keeps its reconnect-required error.

## Impact

- Backend: `_resolve_source_response_candidates` and the HTTP dispatch in `app/modules/proxy/api.py`. It reuses `project_responses_input_for_account_neutral_fresh_replay` and `OwnershipScope`.
- Tests: new route-level regression tests (HTTP both route families, stream and non-stream, WebSocket, pool), plus review of existing replaced-credential tests.

## Non-goals

- Changing the fingerprint definition.
- Recovering compacted conversations or `previous_response_id`-anchored turns.
- Logging pre-dispatch refusals to `request_logs`, or dashboard hints (follow-ups).
