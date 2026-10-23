## ADDED Requirements

### Requirement: Source Responses streams end at their terminal

For a source-routed Responses stream relayed over HTTP/SSE, once the source chunk that completes the stream's first terminal event (`response.completed`, `response.incomplete`, `response.failed` or `error`) has been relayed, the proxy MUST stop reading the source body, close the source response, and end the client stream without waiting for the source to close its body. Bytes in that chunk MUST still be relayed; later source bytes such as `[DONE]`, keepalives or vendor events MUST NOT be awaited. The attempt MUST settle, write its request log and release its admission at that point with the existing terminal classification: a success terminal settles usage, and a failure terminal releases the reservation. A source idle timer or stream error that would only have occurred after the terminal MUST NOT be recorded. Terminal events sharing that chunk are relayed and classified by the existing settlement rules, including the precedence of a failure terminal relayed after a success terminal. Chat-completions source streams MUST keep their existing end-of-stream handling.

#### Scenario: A source keeps its body open after completion
- **GIVEN** a limited key routed to a Responses source that sends `response.created`, an output item, a delta and `response.completed` and then keeps its SSE body open
- **WHEN** the client streams `/v1/responses`
- **THEN** the client stream ends right after `response.completed`, and the source response is closed
- **AND** the request log records `success` with the source usage, the reservation is settled, and no admission remains in flight

#### Scenario: A source keeps its body open after a failure terminal
- **WHEN** the source sends `response.failed` with code `server_is_overloaded` and keeps its body open
- **THEN** the client stream ends after the failure, the row records `error` with `upstream_error_code = server_is_overloaded`, and the reservation is released

#### Scenario: Trailing bytes in the terminal chunk are relayed
- **WHEN** the chunk carrying `response.completed` also carries `data: [DONE]`
- **THEN** the client receives both, and the stream ends without reading further
