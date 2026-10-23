## MODIFIED Requirements

### Requirement: Source WebSocket attempts preserve settlement and safe retry boundaries

Source admission MUST precede quota reservation. Each attempt MUST settle or release exactly once and produce one source-attributed log. Existing source usage policy MUST apply: successful limited-key responses without usage settle an estimate; cancellation after content delivery follows the existing estimate policy; pre-content cancellation and failure/truncated responses release. A portable initial request MAY try at most five distinct eligible sources only for proven pre-send connection failure or eligible handshake rejection. After send begins, ambiguous delivery MUST NOT cause automatic replay, except the single same-source replay of a bridged turn that failed before any event was handed to the client, as defined by "Bridged turns replay one pre-content source failure". Owned continuations MUST NOT switch sources. Prior settlement/admission release MUST finish before cooldown writes or another reservation. A source WebSocket MUST retain transport-level keepalive pings without treating a delayed pong as a response-stream failure; first-frame, stream-idle and total-turn deadlines remain authoritative bounds for stalled work.

#### Scenario: Admission changes during effective-policy lookup
- **WHEN** another request fills a portable initial request's selected source while its effective policy is being checked
- **THEN** preparation MUST retry another eligible candidate within the original deadline and revalidate that candidate's effective policy before reservation
- **AND** an owned continuation MUST NOT switch sources

#### Scenario: A reservation heartbeat encounters a transient database error
- **WHEN** a reservation touch fails transiently during an active generation
- **THEN** later heartbeat intervals MUST retry the touch or terminate the generation with owned cleanup
- **AND** a single failed touch MUST NOT silently stop refresh for the rest of the generation

#### Scenario: Disconnect occurs during an uncertain send
- **WHEN** transmission of `response.create` has begun and the upstream disconnects without a response
- **THEN** the attempt is finalized and no source receives an automatic replay

#### Scenario: A limited-key client leaves after receiving content
- **WHEN** the client disconnects after content delivery and usable terminal usage is absent
- **THEN** existing source estimation/settlement applies once and all admission claims are released

#### Scenario: A usage-bearing terminal is withheld before any delivery
- **WHEN** the client disconnects while a successful terminal with reported usage is waiting for ownership publication or a downstream write lock and no content has been handed to the client transport
- **THEN** the native attempt MUST release its reservation without charging the withheld usage
- **AND** a successful terminal already handed to the transport MUST retain successful settlement

#### Scenario: A connection retry selects a source with a longer timeout
- **WHEN** a portable generation retries a proved pre-send connection failure against an eligible source with a longer timeout
- **THEN** its deadline MUST NOT exceed the earliest source/request deadline already applied to that generation

#### Scenario: A disconnect races terminal delivery
- **WHEN** the client disconnects while a known failure terminal is being published or sent
- **THEN** the attempt releases its reservation even if earlier content or usage was observed
- **AND** a successful terminal handed to the downstream transport retains successful settlement, including warmup input estimation, while a terminal withheld by ownership persistence does not count as delivered

#### Scenario: A terminal send times out after delivery
- **WHEN** a terminal has been handed to the downstream transport and that send later times out or disconnects
- **THEN** the observed terminal retains its accounting result and the session closes without emitting a contradictory second terminal error

#### Scenario: Retry preparation stalls
- **WHEN** source preparation stalls after a pre-send connection failure
- **THEN** the original request deadline bounds the retry preparation and timeout does not reset that deadline

#### Scenario: Provider delays pong while response work is active

- **WHEN** an opted-in source delays its WebSocket pong beyond the transport library's default heartbeat interval while response events remain within the configured first-frame, stream-idle and total-turn deadlines
- **THEN** the proxy MUST keep the source connection available for the response and MUST NOT report `model_source_stream_truncated` solely because the pong was delayed

#### Scenario: Response deadlines still bound a silent source

- **WHEN** a source sends no response event within the configured first-frame or stream-idle deadline
- **THEN** the proxy MUST close the source connection and return its existing timeout error with exactly-once settlement

## ADDED Requirements

### Requirement: Bridged turns replay one pre-content source failure

The first attempt of a WebSocket turn bridged to an HTTP/SSE source MUST hold back its lifecycle prefix: `response.created`, `response.in_progress` and `response.queued` events whose `response.output` is absent or empty, and `response.metadata` events carrying no fields other than `type`, `metadata`, `headers`, `response_id` and `sequence_number`. A held-back event MUST NOT be published to source ownership or handed to the client. When any other `error` or `response.*` event arrives, or when the held-back events exceed the existing 2 MiB withheld-bytes bound, the held-back events MUST be published and delivered first, in source order, the attempt MUST no longer be replayable, and the turn MUST continue as before. A terminal observed while the prefix is being delivered MUST NOT count as handed off until that terminal itself is handed to the client transport. While the prefix is held back, after the source response has delivered its first body bytes, a source body that resets or ends without a terminal event, or a failure terminal whose sanitized upstream error code is `server_is_overloaded`, MUST finalize the attempt as failed (closed response, released reservation and admission, one request log) without delivering its events, and MUST re-send the turn once to the same source, source revision and public model with the same reconstructed request body. The replacement MUST be prepared through regular turn preparation bound to the session identity; when that preparation yields a different effective request body, the replacement MUST be discarded without a request log and the original failure returned. The replacement MUST take a fresh admission claim and reservation, MUST remain bounded by the original turn deadline, and MUST relay its events without holding them back or being replayed again. A `2xx` source response whose body fails before its first chunk MUST keep the existing open-failure handling. No replay MAY occur after any event of the attempt was handed to the client, for any other failure code or error class, for native source sessions, warmups, timeouts, client disconnect, ownership or settlement failure, or while the server drains. When the replacement cannot be prepared, the client MUST receive the original failure as a WebSocket `error` event; a replacement whose reservation is refused MUST be finalized and reported like any refused turn.

#### Scenario: A reset before content is replayed invisibly
- **GIVEN** a bridged session whose source sends `response.created`, `response.in_progress` and `response.metadata` and then resets the connection
- **WHEN** the source answers the replayed request with a complete response
- **THEN** the client receives only the replacement's events, including exactly one `response.created`
- **AND** the source received two identical request bodies, the request log has an error row with `model_source_stream_truncated` followed by a success row, and the first reservation is released while the second is settled

#### Scenario: An overloaded failure before content is replayed
- **WHEN** the first attempt's source stream sends `response.created` followed by `response.failed` with error code `server_is_overloaded`
- **THEN** the client does not receive that failure, the turn is re-sent once, and the first row records `upstream_error_code = server_is_overloaded`

#### Scenario: A failure after content is not replayed
- **WHEN** the source resets the connection after an `response.output_item.added` event was relayed
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
- **WHEN** the held-back lifecycle events exceed the withheld-bytes bound and the source then resets
- **THEN** the client has received those events in order followed by `model_source_stream_truncated`, and no replay occurs
