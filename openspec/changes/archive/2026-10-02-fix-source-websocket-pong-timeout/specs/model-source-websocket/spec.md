## MODIFIED Requirements

### Requirement: Source WebSocket attempts preserve settlement and safe retry boundaries

Source admission MUST precede quota reservation. Each attempt MUST settle or release exactly once and produce one source-attributed log. Existing source usage policy MUST apply: successful limited-key responses without usage settle an estimate; cancellation after content delivery follows the existing estimate policy; pre-content cancellation and failure/truncated responses release. A portable initial request MAY try at most five distinct eligible sources only for proven pre-send connection failure or eligible handshake rejection. After send begins, ambiguous delivery MUST NOT cause automatic replay. Owned continuations MUST NOT switch sources. Prior settlement/admission release MUST finish before cooldown writes or another reservation. A source WebSocket MUST retain transport-level keepalive pings without treating a delayed pong as a response-stream failure; first-frame, stream-idle and total-turn deadlines remain authoritative bounds for stalled work.

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
