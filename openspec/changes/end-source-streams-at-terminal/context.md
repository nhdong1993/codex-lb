# Context: end source streams at their terminal

## Incident (2026-10-23, Asia/Ho_Chi_Minh)

| Evidence | What it shows |
|---|---|
| Direct `curl -N` to `ch-relay` (`127.0.0.1:11502/v1/responses`) | `response.completed` at 2.18 s, after which the body stayed open until the client's own timeout. |
| `ch-relay-source-gateway` JSON log, 16:00–22:30 | 186 of 3,275 `/v1/responses` requests had `request_time` ≥ 290 s, for example `324.289`, `317.119` and `313.613`, with `status=200`. |
| `request_logs` for `src_a5a29b4a…`, last 14 h | 741 HTTP rows `model_source_idle_timeout` ("went idle for 300s"), all with usage, output tokens and `latency_ms` well under 300 s. Input tokens kept growing across consecutive rows of one session, so the client did receive every answer. |

Codex 0.163 does not close the HTTP connection after `response.completed`. `codex-api` `process_sse` runs in a spawned task that keeps reading until EOF or its own idle timeout, so neither side hangs up. Starlette's disconnect listener (ASGI spec 2.3 under uvicorn 0.52) therefore never fires, and the proxy times out first.

## Decisions

- **End at any terminal, success or failure.** This matches the WebSocket bridge, which already closes the source response at its terminal. Clients stop at an `error` or `response.failed` anyway. Closing early also stops relay work such as autocut continuations after an `error` frame.
- **Stop after the chunk that completes the terminal frame.** The parser sets the terminal only when the whole frame has been parsed, so the client always gets the complete terminal plus anything sharing its chunk. A `[DONE]` in a later chunk is dropped. The Responses SSE contract does not use `[DONE]`.
- **Responses shape only.** The chat-completions parser reports no terminal kind, so those streams still run to EOF.
- **Classification is unchanged.** `settlement_stream` already settles a relayed success terminal and releases a failure terminal. The fix only prevents a later idle or stream error from overriding that verdict.
  - Terminal events sharing the terminal's chunk still reach the client and settle under the existing rules. A failure relayed after a success keeps its deliberate precedence (upstream #2208, `test_settlement_stream_relayed_failure_after_a_relayed_success_is_an_error`).
  - A first-terminal latch was considered in review and rejected, because it would change when a limited key is charged.
  - A failure in a separate, later chunk is no longer read at all.

## Example

Source SSE: `response.created`, `response.output_item.added`, `response.output_text.delta`, `response.completed`, and then the body stays open.

- Before: the client gets the four events, then the stream idles for 300 s. The row reads `error model_source_idle_timeout`, the reservation is released, and admission is held for 300 s.
- After: the client stream ends right after `response.completed`, and the source response is closed. The row reads `success` with usage, and the reservation is settled and admission released at once.

## Operations

Measure with `select error_code, count(*) from request_logs where model_source_id = '<source>' and transport = 'http' group by 1`. `model_source_idle_timeout` should drop to genuine stalls only. Gateway `request_time` ≥ 290 s should disappear for completed streams.
