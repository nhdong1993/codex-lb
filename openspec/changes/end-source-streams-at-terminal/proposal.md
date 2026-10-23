## Why

`ch-relay` keeps its SSE response open after `response.completed`. A direct request on 2026-10-23 got the terminal at 2.2 s, and the body was still open minutes later. codex-lb's HTTP source path reads the source body until EOF, so after relaying the terminal it waited for an EOF that never came.

Codex 0.163 reads SSE in a background task that also waits for EOF, so the client kept its connection too. After the 300 s source idle timer:

- the attempt was written as `error model_source_idle_timeout`, although the client had the full answer. On 2026-10-23 this happened 741 times in 14 h on this source.
- a limited key's reservation was released instead of settled, so delivered answers went uncharged.
- the admission claim and the relay connection stayed held. The gateway log shows 186 requests of 290 s or more in 6.5 h.

The WebSocket→HTTP bridge already closes the source response at its terminal; the HTTP route did not.

## What Changes

- A Responses-shaped source stream ends at its terminal. Once the chunk that completes the first source terminal (`response.completed`, `response.incomplete`, `response.failed` or `error`) has been relayed, the proxy stops reading the source body, closes the source response, and ends the client stream.
- Bytes in that same chunk are still relayed. Later bytes are not, for example `[DONE]`, keepalives or vendor frames.
- Settlement, the request log and admission release follow the terminal immediately, with the existing classification: a success terminal settles, a failure terminal releases.
- Terminal events that share the terminal's chunk keep the existing settlement rules. A failure terminal relayed after a success terminal still takes precedence.
- Chat-completions source streams are unchanged; their parser has no terminal kind.
- No schema, setting, API or frontend change.

## Capabilities

### Modified Capabilities

- `model-source-routing`: adds the requirement "Source Responses streams end at their terminal".

## Impact

- `app/modules/model_sources/forwarding.py` (`_source_stream_body`).
- Tests: `tests/integration/test_model_source_dispatch.py`.
