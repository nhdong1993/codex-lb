# Design: Responses WebSocket bridge for HTTP-only model sources

Normative behavior is in the delta specs under `specs/`. This file records the implementation plan and the decisions behind it.

## Current flow

- `responses_websocket` and `v1_responses_websocket` in `app/modules/proxy/api.py` call `_websocket_upstream_transport_denial`. A source-only key whose permitted pool is not entirely native-WebSocket capable (`source_only_key_supports_websockets` → `source_websocket_capabilities` → `catalog.source_websocket_models`) gets HTTP 426. Codex treats 426 as a session-wide HTTP fallback (`codex-rs/core/src/client.rs`, `WebsocketStreamOutcome::FallbackToHttp`).
- Accepted sockets run `proxy_responses_websocket`. `_try_source_responses_websocket` builds one `SourceWebSocketSession` (`app/modules/proxy/source_websocket.py`) per socket. Its `prepare` callback (`_prepare_source_websocket_turn`) keeps only candidates with `supports_responses_websocket`. When none remain it raises `model_source_requires_http_transport` (503).
- `SourceWebSocketSession` opens one upstream WebSocket, sends each turn's `response.create` on it, relays events, publishes ownership before delivery and settles every turn through its own `SourceDispatch`.

## Client protocol facts (Codex 0.163, verified in source)

- `ModelClientSession::prepare_websocket_request` sends `previous_response_id = last_response.response_id` and `input = current.input[len(previous.input) + len(items_added):]` when the previous request's input plus `items_added` is a prefix of the current input and the other request fields are unchanged. `items_added` are exactly the items of `response.output_item.done` events seen before `response.completed`.
- When there is no completed previous response (new connection, failed or incomplete turn, a consumed receiver), the request is full and has no `previous_response_id`. A retry after a failed attempt is therefore always full.
- Prewarm is `response.create` with `generate: false`, using the turn's real input. The next request usually continues from the warmup response id with an empty or short delta.
- A wrapped `error` event with code `previous_response_not_found` is `ApiError::Retryable` ("Retrying the full request"). Other wrapped errors map to an HTTP status (`map_wrapped_websocket_error_event`), and a 5xx status is retried.
- Server item ids with a prefix (`rs_…`, `msg_…`, `fc_…`) are kept when Codex resends history over HTTP, so source output items can be sent back to the source unchanged.

## Decisions

### D1. Upstream mode per session

`_prepare_source_websocket_turn` computes `native = [s for s in resolved.sources if s.supports_responses_websocket]`, then:

- bound session: keep `bound.upstream`. For `websocket`, use the native pool; for `http`, use `resolved.sources`. In both cases filter to `bound.source_id` and `bound.revision`.
- unbound with `native` nonempty: `websocket` over `native` (today's behavior).
- unbound with `resolved.sources` empty: keep today's 503 `model_source_requires_http_transport`. This happens when the selected model has only non-streaming Responses sources: `_select_responses_model_source_with_continuity` runs with `require_streaming=False`, and `_resolve_source_response_candidates` then filters by streaming because `payload.stream = True`. Ownership errors for non-streaming continuations still come first from the resolver, as today.
- otherwise: `http` over all `resolved.sources`, which are by construction streaming Responses sources.

`SourceSocketIdentity` and `SourceWebSocketTurn` gain `upstream: Literal["websocket", "http"]`. A bound session never changes mode, source or revision; a mismatch keeps the existing 409 `websocket_reconnect_required`. Mixed pools prefer native, as before. The bridge is used only when no eligible candidate declares native support.

The `disabled` branch always raises `model_source_disabled`. Subscription-anchor refusals (`reject_source_only_anchor`) are unchanged.

### D2. Transcript reconstruction happens at the client-payload level, before `prepare`

The session reconstructs exactly what Codex would have sent over HTTP. It then hands that full client payload to the same `prepare` used for every other turn. Ownership keys, alias resolution, overrides, tool filtering, quota estimation and size checks therefore see the full body, just as for an HTTP full resend. Output items published by the previous turn's `SourceOwnershipRecorder.record_event` pin the expanded request to the same source and revision.

State (bridge sessions only) is `_BridgeTranscript(response_id, items_json, size)`:

- `items_json` is the compact UTF-8 JSON array (`ensure_ascii=False`) of the turn's full client input followed by its `response.output_item.done` items as delivered to the client. Text is stored rather than parsed objects, which bounds idle memory near the byte size.
- It is replaced only on `response.completed`. Any other terminal, an error or a size overflow clears it.
- `size` must stay within `request_body_limit_for_path("/v1/responses")`, the HTTP ingress bound for an equivalent full resend. A larger transcript is not kept.

Expansion runs in `_worker` for each queued turn when `identity.upstream == "http"`:

- no `previous_response_id`: the payload passes through unchanged.
- `previous_response_id == transcript.response_id`: drop the field and set `input = json.loads(items_json) + delta`. A string input is normalized to `[{"role": "user", "content": text}]`. Any other input shape is rejected with `invalid_request_error`. An expanded size above the bound is rejected with `invalid_request_error` before `prepare`.
- any other id, or no transcript: the payload passes through unchanged to `prepare`. Subscription-anchor refusals (`model_source_requires_http_transport`), security routing and ownership errors keep their precedence. Once `prepare` has resolved an `http` turn, a remaining client `previous_response_id` raises the continuity error before admission. Its fields come from `_websocket_continuity_error_fields(reason="previous_response_not_found", expose_stale_previous_response_classifier=...)`, with status 502, matching the native `_terminal_error` mapping. No source is contacted and no reservation is made.

The same `prepare` check covers a first turn that resolves to `http` with a client `previous_response_id`, which cannot be connection-local. A bridged request therefore never forwards a client `previous_response_id`. Effective-payload overrides are still forwarded as on HTTP.

The turn records the input it was prepared from (`turn.client_input`) so the next transcript can be built after completion.

Rejected alternative: forwarding unknown ids to the source. Some OpenAI-compatible relays silently ignore `previous_response_id`, which would produce an answer from a truncated context. Failing closed also gives Codex its full-resend retry.

### D3. Bridged generation (one HTTP request per turn)

`SourceWebSocketSession` receives an injected `open_http` callable from `api.py`. Injection avoids a circular import, because the SSE block reassembler `_iter_source_sse_event_blocks` lives in `api.py`. The callable:

- calls `stream_source_responses(owner.source, http_payload, scheduler=owner.scheduler, clock=owner.clock)` with `http_payload = effective payload − {"generate"}` and `stream=True`. The header deadline, first-frame deadline, status-error redaction, credential recoding and idle cap are the existing HTTP ones;
- reassembles blocks with `_iter_source_sse_event_blocks(..., max_event_bytes=MAX_MESSAGE_BYTES)`;
- maps `aiohttp.ClientError` during the body to `model_source_stream_truncated` (502) and `StreamEventTooLargeError` to `model_source_invalid_event` (502);
- returns `BridgedSourceEvents(blocks, upstream_status_code, aclose)`. `aclose` closes the block generator and then `SourceResponsesStream.aclose()`, which is the transport latch.

Worker open loop (shared with native):

```
await self._reserve(turn)            # skipped for bridged warmups (D4)
while True:
    attempted.add(turn.owner.source.id)
    try:
        if turn.upstream == "http": self._http = await wait_for(open_http(...), deadline)
        elif self.upstream is None: self.upstream = await open_source_websocket(...)
        break
    except ModelSourceForwardingError as error:
        turn = await self._retry_elsewhere(turn, error, attempted, raw)   # existing rules
self.identity = turn.identity
```

`_retry_elsewhere` is the existing failover body, moved without behavior change for native turns. It now also requires `self.identity is None`, so a bound bridged session never moves sources. For HTTP, the retry decision matches the HTTP path's `retryable_source_error` and portability rules. Bridged turns get one addition so that the HTTP pool contract (`_balanced_source_responses_response` returns `last_error` when `pool.choose` finds nothing) is kept. If re-preparation with `excluded=attempted` fails with `model_source_busy`, meaning no replacement is currently selectable, the original forwarding error is raised instead. For example, a single source answering 429 yields its redacted 429 rather than `503 model_source_busy`. Any other revalidation error (policy, ownership, security routing, disabled source) is raised as it is. The failed attempt has already finished and released its reservation before re-preparation, so release happens once.

The HTTP open runs under `scheduler.wait_for(..., timeout=max(0, turn.deadline - now))`. `_open_source_stream` already turns its own header, first-frame and transport failures into `ModelSourceForwardingError`, so a `TimeoutError` escaping the open can only be the turn deadline. The worker catches it explicitly. The cancelled open closes its exit stack (the `BaseException` path in `_open_source_stream`). The worker then calls `finish_with_forwarding_error(model_source_timeout, 504)` and raises it with no failover and no replay, because the request may have been submitted. Finalization therefore no longer depends on whether the lifecycle watcher has already set `deadline_expired`. If the watcher wins instead, the existing `_finish_interrupted` path classifies the same `model_source_timeout`.

`_relay_http(turn)` iterates the blocks:

- `extract_sse_data(block)` returning `None` (comment, keepalive, `[DONE]`) is skipped;
- data that is not a JSON object, or has no string `type`, or carries `stream_id`, fails with `model_source_invalid_event`;
- typed events other than `error` and `response.*` (for example `codex.rate_limits`) are dropped;
- everything else goes through the per-event body extracted from `_relay` into `_relay_event`: envelope validation, `first_frame_at`, `SourceStreamUsageParser.observe_event` (model identity restore), failure sanitization via `_terminal_error`, `ownership.record_event` before `send`, `observe_stream`, and `send(event, turn=turn)` for the existing handoff/content accounting.

`response.output_item.done` items are collected for the transcript. On a terminal the transcript is updated (D2), then the HTTP stream is closed so admission is never returned while the connection is open, and then the dispatch finishes. Success uses `upstream_status_code=events.upstream_status_code`; failure uses `finish_with_forwarding_error`. Settlement failures raise as today. EOF before a terminal raises `model_source_stream_truncated`.

`SourceDispatch` uses `transport="websocket"` and `upstream_transport="openai_compatible_http"`. `owner.event_usage` is the bridge's own holder (as native). The stream body's internal parser holder is not used for handoff decisions: it parses whole chunks ahead of delivery and could mark a terminal before earlier events in the same chunk are sent.

`_close_upstream()` closes the native socket and, if present, the active `BridgedSourceEvents`. Every existing timeout, disconnect, drain and cleanup path therefore closes the HTTP response before finishing the dispatch.

### D4. Bridged warmup

HTTP Responses has no `generate:false`. A bridged warmup turn runs the normal `prepare`, which covers routing, policy, ownership, admission claim and dispatch owner. The worker then skips reservation and the upstream entirely. In order, it:

1. binds `self.identity = turn.identity` (source, revision, model, `http`). This is the warmup's equivalent of a successful open; the transcript expansion and the next `prepare(bound=...)` both depend on it. A bridged generation binds after its first successful HTTP open, so failover can still move an unbound first turn;
2. stores the transcript `(id, input)`;
3. sends a synthesized `response.created` and `response.completed` pair (`id=resp_<uuid4 hex>`, `object=response`, public model, empty output, no usage);
4. calls `discard()`.

The next create can only be dequeued after the worker loop resumes, which happens after steps 1–4. An immediate continuation therefore always sees both the binding and the transcript.

`SourceDispatch.discard()` is new. It marks the dispatch finished and releases its admission claim once as `inconclusive`. It writes no request-log row and no dispatch metric, because nothing was dispatched. The no-log guarantee must hold on every exit, not only in the worker. `run()` can finish a prepared `first` turn whose worker never started (disconnect, drain or deadline during the preparation-to-worker handoff) through `_finish_interrupted()`. `_finish_interrupted()` therefore starts with `if turn.upstream == "http" and turn.owner.warmup: await turn.owner.discard(); return`. Every path, including the worker's `finally` and the session `cleanup()`, already ends there. Native warmup accounting is unchanged, and the delta modifies the bounded-profile requirement to say so.

### D5. Discovery and handshake

- `catalog.source_websocket_models`: a model is WebSocket-capable when its source is an enabled Responses source and the model is enabled and streaming. The native flag is no longer required. `source_websocket_capabilities`, `source_only_key_supports_websockets`, the catalog `prefer_websockets` and the key-dashboard installer flag follow automatically.
- `_websocket_upstream_transport_denial` subscription-outage branch: `capable_models` drops the native requirement.
- Explicit global upstream transport `http` still refuses every ordinary handshake with 426, so operators keep a kill switch with no new setting.

## Failure modes

| Situation | Behavior |
|---|---|
| Source HTTP 4xx/5xx before the stream | WebSocket `error` event with the HTTP route's redacted envelope and status. First portable turn: retry rules as on HTTP, and when no replacement is selectable the original error is returned, not `model_source_busy`. Bound: the session ends. |
| Turn deadline expires while the HTTP request is opening | The open is cancelled and its transport closed, then `finish` with 504 `model_source_timeout`. No failover or replay. |
| In-stream `error`/`response.failed` | Sanitized like native (`model_source_response_failed` or the continuity classifier). The transcript is cleared and the session continues. |
| Body drops mid-stream | `model_source_stream_truncated`, existing cancellation accounting. The session ends. |
| Silent source | Existing first-frame (30 s), idle cap (≤300 s), source total budget and turn deadline. |
| Client leaves mid-turn | The HTTP response is closed, then `finish(cancelled)` with the existing delivered-content rules. |
| Continuation id unknown or stale | Continuity error, no source contact, no reservation. Codex retries with full input. |
| Transcript beyond the HTTP body bound | Not kept. The next continuation gets the continuity error. A first create above 16 MiB keeps the existing limit. |
| Replica restart or reconnect | The transcript is lost. Codex starts the new connection with a full request. |
| Model has only non-streaming sources | Unchanged: `model_source_requires_http_transport` after upgrade, and 426 at the handshake for source-only keys. |
| Client leaves between warmup preparation and execution | `_finish_interrupted` → `discard()`: admission released once, no row or metric. |

## Example

1. Codex connects to `/v1/responses` with a key permitted to `ch-relay/gpt-6-astra` on an HTTP-only source. The handshake is accepted.
2. Codex sends `{"type":"response.create","model":"ch-relay/gpt-6-astra","generate":false,"input":[U1],…}`. The proxy answers `response.created`/`response.completed` with `resp_w`, stores `[U1]`, and sends nothing upstream.
3. Codex sends `previous_response_id: resp_w, input: []`. The proxy expands this to `input: [U1]` and POSTs `/v1/responses` (stream) to the source. It relays `response.created`, deltas, `response.output_item.done` (reasoning `rs_1`, function call `fc_1`/`call_1`) and `response.completed` (`resp_1`). It stores `[U1, rs_1, fc_1]`.
4. Codex sends `previous_response_id: resp_1, input: [function_call_output(call_1)]`. The proxy POSTs `input: [U1, rs_1, fc_1, output(call_1)]` with no `previous_response_id`.

## Verification plan

- Targeted pytest, one process at a time with `-n` ≤ 2 (production host): new bridge integration tests, the updated existing websocket/handshake/catalog/installer tests, and unit tests for transcript expansion and `discard()`.
- `uv run ruff check`, `ruff format --check`, the project type checker on touched files, `openspec validate bridge-source-websocket-over-http --strict`.
- Local real-client acceptance: run Codex CLI 0.163 against an isolated dev instance (SQLite, separate port) backed by a local HTTP/SSE stub source. Use an isolated `CODEX_HOME` and `supports_websockets = true`, with stdin from `/dev/null`. The stub source returns a `function_call` on the first generation and a final message after the tool output, so Codex has to continue. Evidence is collected on both legs:
  - client leg: a small logging WebSocket/HTTP relay between Codex and the dev instance. It records the accepted upgrade (101), each client `response.create` (`generate`, `previous_response_id`, input item count and types), every terminal event returned, and every client HTTP request. Required: a `generate:false` create, at least one incremental create whose `previous_response_id` equals the preceding `response.completed` id, a successful `response.completed` for it, and zero client `POST …/responses` over HTTP during the scenario;
  - source leg: the stub's captured POST bodies. Required: no `previous_response_id`, `generate` or `type`; the second body's input equals the first body's input, then the delivered output items, then the client's delta;
  - the dev instance's request logs show `transport=websocket`, `upstream_transport=openai_compatible_http` for each generation and no row for the warmup.
  Record the redacted evidence in `verification.md`.
