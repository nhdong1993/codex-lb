## Why

On 2026-10-21, Codex CLI 0.163 auto-compaction failed three times in one session that used `ch-relay/gpt-6-astra`, a model served only by the HTTP-only source `ch-relay (VPS)`. Each failure returned the terminal error "The 'ch-relay/gpt-6-astra' model is not supported when using Codex with a ChatGPT account."

Codex sends remote compaction as a `response.create` over its Responses WebSocket, with a terminal `compaction_trigger` as the last input item. `_prepare_source_websocket_turn` treats that trigger as a structural subscription exclusion and returns the turn to the subscription path:

- on a socket already bound to the bridged source session, the turn gets 409 `websocket_reconnect_required`;
- Codex reconnects and resends the full context; the first turn of the new socket goes to a ChatGPT account, which rejects the source-only slug with a terminal 400.

Request logs for the three failures show `transport=websocket` and no `model_source_id`, while every ordinary turn of the same session was bridged to the source. The exclusion dates from 2026-10-07, when HTTP compaction moved to model sources and WebSocket was explicitly left alone because WebSocket could not reach HTTP-only sources yet. The HTTP/SSE bridge (`bridge-source-websocket-over-http`) made those sources reachable, but compaction turns kept the old exclusion.

## What Changes

- On the direct Responses WebSocket, a terminal `compaction_trigger` no longer excludes a turn from source dispatch. Compaction turns follow the same source routing, ownership, continuation, admission, reservation, settlement and relay rules as other turns on native and bridged source sessions, the same as HTTP compaction already does.
- A compaction turn on a socket bound to a source session stays on that session instead of receiving `websocket_reconnect_required`. On a bridged session, a compaction that continues the last completed response is expanded from the connection transcript like any other continuation.
- Source WebSocket request logs record `request_kind=compaction` for these turns, matching HTTP source dispatch.
- A completed bridged compaction response does not become the socket's continuation state. A continuation that names it gets the route's continuity error, and Codex resends its compacted history in full. Replaying the stored input would put the request-only trigger in the middle of the input (a local 400) and would resend the history that the compaction replaced.
- A compaction turn for a source-only model that carries a recorded subscription anchor now receives the service-level 503 `model_source_requires_http_transport`, like other turns. Before, it went to the anchored ChatGPT account, which always rejects a source-only model with a terminal 400.
- A compaction turn for a disabled source's model receives `model_source_disabled`, like other turns, instead of reaching a subscription account.
- Uploaded `input_file` references, required-capability security routing and recorded owners of subscription-registry models keep their precedence. HTTP behavior and the subscription WebSocket guards are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-source-websocket`: compaction turns are ordinary source turns on native and bridged source sessions; request logs carry `request_kind=compaction`; a completed bridged compaction clears the continuation state.
- `responses-api-compat`: remove the terminal `compaction_trigger` from the WebSocket structural exclusions in the ownership, route-compatibility and disabled-source requirements.

## Impact

- Backend: `_prepare_source_websocket_turn` in `app/modules/proxy/api.py` calls `responses_source_route_excluded(payload, exclude_compaction=False)` and passes `request_kind` to `SourceDispatch`. `_remember` in `app/modules/proxy/source_websocket.py` does not store a transcript for a compaction turn. The `responses_source_route_excluded` docstring in `app/modules/proxy/request_policy.py` is updated. The subscription WebSocket guards in `app/modules/proxy/_service/websocket/mixin.py` keep their default.
- Tests: public-route WebSocket regressions for first-turn and bound bridged compaction, continuation after a bridged compaction, native compaction, the subscription-anchored refusal and the disabled-source refusal. The existing test that pinned a subscription-anchored source-only compaction to the subscription path is updated.
- Docs: `docs/model-source-websocket.md` and `openspec/specs/model-source-websocket/context.md`.
- No migration, setting, schema, dashboard or client-visible envelope change. `model_source_requires_http_transport` and `model_source_disabled` are existing error codes.

## Non-goals

- Changing HTTP routing, including the HTTP recorded-owner veto for source-only models.
- Collecting WebSocket compaction into the standalone `response.compaction` JSON contract. WebSocket compaction stays a streamed Responses turn.
- Validating source compaction output on WebSocket beyond the bridge's existing event checks.
