## MODIFIED Requirements

### Requirement: Bridged turns replay one pre-content source failure

The first attempt of a WebSocket turn bridged to an HTTP/SSE source MUST hold back every event until its first visible output. Held-back events are the lifecycle prefix and output-free events. The lifecycle prefix is `response.created`, `response.in_progress` and `response.queued` events whose `response.output` is absent or empty, and `response.metadata` events carrying no fields other than `type`, `metadata`, `headers`, `response_id` and `sequence_number`. Output-free events are: `response.output_item.added` and `response.output_item.done` whose item `type` is `reasoning`; every `response.reasoning_summary_part.*`, `response.reasoning_summary_text.*` and `response.reasoning_text.*` event; and, while all text of an assistant `message` is empty after trimming whitespace, `response.output_item.added` and `response.output_item.done` of that `message`, `response.content_part.added` and `response.content_part.done` with empty text, and `response.output_text.delta`, `response.output_text.done`, `response.refusal.delta` and `response.refusal.done` with empty text. Every other `error` or `response.*` event, including an unknown event type, is visible output. A held-back event MUST NOT be published to source ownership or handed to the client. When visible output arrives, or when the held-back events exceed the existing 2 MiB withheld-bytes bound, the held-back events MUST be published and delivered first, in source order, the attempt MUST no longer be replayable, and the turn MUST continue as before. A terminal observed while held-back events are being delivered MUST NOT count as handed off until that terminal itself is handed to the client transport. While events are held back, after the source response has delivered its first body bytes, a source body that resets or ends without a terminal event, or a failure terminal whose sanitized upstream error code is `server_is_overloaded`, MUST finalize the attempt as failed (closed response, released reservation and admission, one request log) without delivering its events, and MUST re-send the turn once to the same source, source revision and public model with the same reconstructed request body. A `response.completed` terminal that arrives while every earlier event of the attempt is still held back, and whose `response.output` holds only reasoning items and assistant messages without non-empty text or refusal, is an empty completion: the attempt MUST be finalized as a success that settles its reported usage, or the existing estimate when a limited key lacks reported usage, with `error_code = model_source_empty_completion` on its request log and an `inconclusive` trial result, MUST NOT be published to source ownership or kept as a continuable transcript, MUST NOT deliver any of its events, and the turn MUST be re-sent once like a replayable failure. A `response.incomplete` terminal MUST release the held-back events and MUST NOT be replayed. The replacement MUST be prepared through regular turn preparation bound to the session identity; when that preparation yields a different effective request body, the replacement MUST be discarded without a request log and the original failure returned. The replacement MUST take a fresh admission claim and reservation, MUST remain bounded by the original turn deadline, and MUST relay its events without holding them back or being replayed again. A `2xx` source response whose body fails before its first chunk MUST keep the existing open-failure handling. No replay MAY occur after any event of the attempt was handed to the client, for any other failure code or error class, for native source sessions, warmups, timeouts, client disconnect, ownership or settlement failure, or while the server drains. When the replacement cannot be prepared, the client MUST receive the original failure as a WebSocket `error` event, which is `model_source_empty_completion` with status 502 for an empty completion; a replacement whose reservation is refused MUST be finalized and reported like any refused turn.

#### Scenario: A reset before content is replayed invisibly
- **GIVEN** a bridged session whose source sends `response.created`, `response.in_progress` and `response.metadata` and then resets the connection
- **WHEN** the source answers the replayed request with a complete response
- **THEN** the client receives only the replacement's events, including exactly one `response.created`
- **AND** the source received two identical request bodies, the request log has an error row with `model_source_stream_truncated` followed by a success row, and the first reservation is released while the second is settled

#### Scenario: An overloaded failure before content is replayed
- **WHEN** the first attempt's source stream sends `response.created` followed by `response.failed` with error code `server_is_overloaded`
- **THEN** the client does not receive that failure, the turn is re-sent once, and the first row records `upstream_error_code = server_is_overloaded`

#### Scenario: A reset during reasoning is replayed
- **WHEN** the first attempt's source stream sends `response.created` and a reasoning item and then resets the connection
- **THEN** the client receives only the replacement's events and the first row stores `failure_detail = source_bridge events=created,output_item handed_off=none replay=eligible`

#### Scenario: A failure after content is not replayed
- **WHEN** the source resets the connection after a non-empty `response.output_text.delta` was relayed
- **THEN** the client receives `model_source_stream_truncated` and the source receives no second request

#### Scenario: Other failure codes are not replayed
- **WHEN** the first attempt fails before content with a failure terminal whose code is `server_error`
- **THEN** the client receives the held-back events followed by the sanitized failure, and no replay occurs

#### Scenario: The replacement fails too
- **WHEN** both the first attempt and its replacement reset before content
- **THEN** the client receives the replacement's `response.created` and `model_source_stream_truncated`, the source receives exactly two requests, and both rows are errors with released reservations

#### Scenario: The replacement cannot be admitted
- **WHEN** the first attempt resets before content and the bound source has no free admission for the replacement
- **THEN** the client receives the original `model_source_stream_truncated` error and only the first attempt is logged

#### Scenario: Refreshed policy changes the replacement body
- **WHEN** the first attempt resets before content and the source's request overrides changed after it was dispatched
- **THEN** no second request is sent and the client receives the original `model_source_stream_truncated` error

#### Scenario: An outsized prefix is relayed
- **WHEN** the held-back events exceed the withheld-bytes bound and the source then resets
- **THEN** the client has received those events in order followed by `model_source_stream_truncated`, and no replay occurs

#### Scenario: An empty completion is replayed invisibly and charged
- **GIVEN** a bridged session whose source sends `response.created`, a reasoning item, an assistant `message` whose only text is `""`, and `response.completed` with usage of 11 input and 5 output tokens
- **WHEN** the source answers the replayed request with a message whose text is `done`
- **THEN** the client receives only the replacement's events, including exactly one `response.created`, and the source received two identical request bodies
- **AND** the request log has a `success` row with `error_code = model_source_empty_completion`, 11 input and 5 output tokens, followed by a `success` row without an error code, and both reservations are settled

#### Scenario: Reasoning followed by visible output is delivered in order
- **WHEN** the first attempt sends a reasoning item and then a non-empty text delta or a function call item
- **THEN** the client receives the reasoning item before that output, in source order, and no replay occurs

#### Scenario: A completion that carries its answer only in the envelope is delivered
- **WHEN** the first attempt sends `response.created` and then `response.completed` whose `response.output` holds a message with text `done`, without any output-item events
- **THEN** the client receives both events and the source receives one request

#### Scenario: An incomplete answer after reasoning is not replayed
- **WHEN** the first attempt sends a reasoning item and then `response.incomplete`
- **THEN** the client receives those events unchanged and the source receives one request

#### Scenario: The replacement completes empty too
- **WHEN** both the first attempt and its replacement complete empty
- **THEN** the client receives the replacement's events unchanged, the source receives exactly two requests, and only the first row carries `model_source_empty_completion`

#### Scenario: An empty completion whose replacement cannot be admitted
- **WHEN** the first attempt completes empty and the bound source has no free admission for the replacement
- **THEN** the client receives the WebSocket error `model_source_empty_completion` and only the first attempt is logged, as a success with its usage
