# WebSocket compaction through model sources

## Incident

Codex CLI 0.163 on 2026-10-21, model `ch-relay/gpt-6-astra` (HTTP-only streaming Responses source, served to WebSocket clients through the HTTP/SSE bridge). The session's ordinary turns were bridged to the source. When the context limit was reached, Codex started "remote compaction v2" over the same Responses WebSocket:

1. 17:08:31 UTC, same socket: `response.create` with a terminal `compaction_trigger`. The source session's preparation returned the turn to the subscription path because of the trigger, so the bound session answered 409 "Reconnect to change the session model or backend".
2. Codex reconnected and resent the full history plus the trigger. On the new socket the turn went through subscription account selection, and the ChatGPT upstream answered 400 `invalid_request_error`: "The 'ch-relay/gpt-6-astra' model is not supported when using Codex with a ChatGPT account."
3. The same failure repeated at 17:14:30 and 17:15:10 as pre-sampling compaction on the next user turns.

All three request-log rows have `transport=websocket`, `status=error` and no `model_source_id`.

## Why the exclusion existed

`fix-model-source-compaction` (2026-10-07) moved HTTP terminal triggers and the standalone compact endpoints to model sources and stated "Keep WebSocket's existing structural compaction behavior outside this HTTP correction". At that time HTTP-only sources were not reachable over WebSocket at all. `bridge-source-websocket-over-http` (2026-10-18) changed that, but kept the trigger as a structural exclusion. The subscription path cannot serve a source-only model, so every compaction of a bridged session failed.

## Decision

The trigger is no longer a structural exclusion in source WebSocket preparation. A compaction turn is routed like any other source turn:

- a bridged session forwards it as one streaming HTTP Responses request, and the source answers with its own compaction output (ch-relay supports a terminal trigger on `/v1/responses`);
- a native session forwards the create frame unchanged;
- subscription anchors keep their existing meaning: a registry model stays with its recorded owner, and a source-only model is refused with `model_source_requires_http_transport` so Codex retries over HTTP.

This is the same rule HTTP has used since 2026-10-07 (`exclude_compaction=False`).

The subscription WebSocket guards in `mixin.py` keep the default exclusion. The source handler runs first for every `response.create`, so those guards only see compaction turns that source preparation already returned to the subscription path (capability routing, registry-model anchors, file pins).

### Continuation after a bridged compaction

The implementation review (review-impl-20261021-001, round 1) showed that the ordinary transcript rule broke continuation after a compaction. The stored input `[history…, compaction_trigger]` plus the output `[C1]` expands a continuation into `[history…, compaction_trigger, C1, U2]`. Trigger validation rejects that input locally with 400. The operator chose on 2026-10-21 to clear the continuation state after a completed bridged compaction (option A). The alternative was to store the input without the trigger (option B).

- A: a continuation that names the compaction response gets the route's continuity error, the same as after a reconnect or a failed response. Codex resends its own compacted history in full. It costs one extra round trip and makes no assumption about how a source treats history before a compaction item.
- B (rejected): the source would receive the whole pre-compaction history again next to the compaction item. That can overflow the context the compaction was meant to shrink.

The continuity error ends a bound bridged session (existing behavior), so Codex reconnects before the full resend.

## Failure modes

- Source failure during compaction: relayed like any bridged turn failure (`response.failed` or an error event). Codex reports the compact error; no subscription retry happens.
- Subscription-anchored source-only compaction: 503 refusal over WebSocket. Over HTTP, the recorded-owner veto still applies (a known gap shared with ordinary turns).
- Continuation of a bridged compaction response: continuity error, then a full resend from Codex.
- The WebSocket path does not apply the standalone compact collector. A source that ends the stream without a compaction item completes the turn as the source reported it.

## Example

Bridged socket for `ch-relay/gpt-6-astra`:

1. Turn 1: input `[U1]`, completed as `resp_1` with output item `M1`.
2. Codex compacts: `previous_response_id: resp_1`, input `[{"type":"compaction_trigger"}]`.
3. The bridge expands the continuation. The source receives `input: [U1, M1, {"type":"compaction_trigger"}]`, `stream: true`, no `previous_response_id`.
4. The source streams `response.output_item.done` with a `compaction` item and `response.completed`. The client receives them with the public model; the request log records `request_kind=compaction`, `transport=websocket`, `upstream_transport=openai_compatible_http` and the source id.
