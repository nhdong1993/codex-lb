## ADDED Requirements

### Requirement: Source keepalive resources remain bounded without pongs

Source WebSocket keepalive MUST consume bounded bookkeeping resources independent of the number of successful turns or unanswered pings on a reused connection. Periodic transport pings MUST continue without a pong deadline. Delayed pongs MUST NOT corrupt subsequent turns, and connection closure MUST terminate its keepalive work. Existing response deadlines, ownership, no-replay and settlement rules MUST remain in effect.

#### Scenario: Reused source never answers pings
- **WHEN** a source completes repeated turns without answering transport pings
- **THEN** successful responses and connection reuse MUST continue while keepalive bookkeeping stays bounded independently of turn count

#### Scenario: Provider resumes pong delivery
- **WHEN** a source sends delayed pong frames after completing a response
- **THEN** the connection MUST remain usable for the next owned continuation

#### Scenario: Source connection closes
- **WHEN** the source connection closes after success, timeout, peer closure or client cancellation
- **THEN** its keepalive work MUST terminate and MUST NOT retain pending pong state
