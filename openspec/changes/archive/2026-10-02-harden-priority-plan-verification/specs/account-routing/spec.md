## ADDED Requirements

### Requirement: Reused WebSockets respect model exclusion

Before dispatching a new response.create on an existing upstream WebSocket, routing MUST apply current account/model rejection evidence. A movable turn MUST re-enter selection if its account/model pair is excluded. A hard file or conversation owner MUST remain authoritative and fail closed when excluded. Accepted sibling turns MUST NOT be interrupted to move a newly excluded turn. Unrelated models and expired evidence MUST remain eligible for reuse.

#### Scenario: Peer rejects the model on an idle reused socket
- **WHEN** another request records a model rejection for account A and a new movable request for that model arrives on an idle socket using A
- **THEN** A receives no new frame and another eligible account can serve the request

#### Scenario: Exclusion while a sibling is accepted
- **WHEN** a new excluded turn arrives while another accepted turn is using the socket
- **THEN** only the unsent turn is rejected and the accepted turn can complete

#### Scenario: Excluded hard owner
- **WHEN** an excluded account/model pair belongs to the required conversation or file owner
- **THEN** the request fails without sending to that account or moving ownership
