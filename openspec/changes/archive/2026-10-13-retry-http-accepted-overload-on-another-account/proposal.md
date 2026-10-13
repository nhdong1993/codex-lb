## Why

Since 2026-10-08, upstream has been rejecting Plus-account admissions with `server_is_overloaded` during the 01:00-15:00 UTC peak. These rejections reach clients directly over the direct HTTP/SSE Responses path (`/backend-api/codex/responses` and `/v1/responses` over upstream HTTP). Production request logs for 2026-10-11..13, Plus accounts, peak hours:

| surface | overload rate |
|---|---|
| direct HTTP/SSE (every request is a fresh upstream admission) | 19.8 % |
| WebSocket first turn on a new upstream connection | 10.5 % |
| WebSocket follow-up turn on an open upstream connection | 1.8 % |

Across 48 h the direct HTTP path surfaced 1,108 overload terminals. They arrived 2-27 s after dispatch (p50 4 s), and every one reported zero output. Only 7 of 591 sampled overloaded requests reselected an account. The client gets a terminal error for a turn that produced nothing, and the agent stops mid-task. Example: request `0d54ba48-6910-4fa1-bd37-9a3847deed47`. It went `gpt-6-sol` -> account `b6a2d2ec…`, received `response.failed` with `server_is_overloaded` after 4.9 s with no output, and that failure was surfaced to the client.

The HTTP bridge and direct WebSocket surfaces already replay accepted, output-free capacity failures once (`retry-accepted-output-free-capacity-failures`). That change deliberately left the direct SSE path fail-closed: the requirement "Model-capacity messages are retryable transient failures" says a serialized capacity event MUST surface without re-POSTing, because an upstream response id alone cannot prove the POST is safe to replay. This change gives the direct SSE path the same output-free proof the other surfaces already accept. A capacity terminal that reports no output items and no billed output or reasoning tokens, arriving before any model-output event, proves the turn had no side effect.

## What Changes

- Scope: direct HTTP/SSE Responses streams whose request can move to another account. That means no `previous_response_id`, no file pin, no turn-state owner, no required preferred account, not the `single_account` strategy, and deterministic failover enabled.
- Hold the upstream lifecycle prelude for these streams. The prelude is everything before the first model-output or other non-prelude `response.*` event: `response.created`, `response.in_progress`, `response.queued`, and non-`response.*` metadata frames. The held frames are released in their original order as soon as any other event arrives, so a turn that produces output is forwarded unchanged. Only the moment the prelude reaches the client moves.
- If the next event is an output-free capacity terminal (`server_is_overloaded`, `overloaded_error`, `model_at_capacity`, or the selected-model capacity message) and the terminal reports no output, discard the held prelude. Record the account's overload health (deferred behind API-key settlement as today), exclude the account, and re-send the request once on another account through the existing pre-visible failover path. The client sees only the replacement's lifecycle.
- A capacity terminal that is the *first* upstream event (no `response.created`) gets the same single replay under the same proof. **BREAKING (contract):** this reverses the scenario "Serialized selected-model capacity event surfaces without replay" for eligible requests.
- At most one capacity replay per request. When the replay also fails output-free, or no alternate account is selectable, the client receives the original capacity terminal unchanged. It never receives a synthetic `no_accounts` error.
- Quota and rate-limit codes, `server_error`, transport/body-read failures, and any failure after model output keep their existing fail-closed handling. Requests that cannot move keep today's behavior exactly, with no prelude hold.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `responses-api-compat`: direct HTTP/SSE streams replay one output-free capacity terminal on another account within a single visible lifecycle. The "serialized capacity event surfaces without replay" scenario is narrowed to requests that cannot move or that fail the output-free proof.

## Impact

- `app/modules/proxy/_service/streaming/mixin.py` (`_stream_once` prelude hold and capacity classification, which must stay within the architecture line ceiling) and `app/modules/proxy/_service/streaming/retry.py` (eligibility, one-replay budget). A new helper module under `app/modules/proxy/_service/streaming/` will hold the hold/classify logic. It reuses `_terminal_payload_reports_output` and the capacity code set from `http_bridge/accepted_replay.py`.
- Tests: `tests/integration/test_proxy_transient_retry.py` (`test_stream_overload_alias_surfaces_without_replay` changes meaning; new multi-account replay, no-alternate, second-failure, output-before-failure, pinned-request, and API-key settlement-order cases) plus unit coverage for the helper.
- No API, schema, migration, dependency, configuration, or dashboard change. The failed attempt keeps its own request-log row with `server_is_overloaded`, so overload stays observable. The replacement attempt logs normally.
