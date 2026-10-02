## ADDED Requirements

### Requirement: Asynchronous model admission preserves unsent transport ownership

A direct WebSocket turn MUST recheck transport retirement after asynchronous model admission. A turn whose transport closed before dispatch MUST remain unsent and use the existing reconnect path without consuming its post-send replay budget or penalizing account health.

#### Scenario: Socket closes during model lookup
- **WHEN** the reader observes upstream closure while a new turn awaits model admission
- **THEN** the sender does not send that turn to the retired socket and can complete it through a replacement socket

### Requirement: HTTP bridge reuse respects shared model rejection

HTTP bridge requests MUST apply shared account/model exclusion when reusing a session and before dispatch after admission waits. Movable requests MUST be able to re-enter selection; strict conversation or file owners MUST fail closed without crossing accounts. A rejection discovered after admission MUST settle the unsent request without interrupting accepted siblings or penalizing global account health. Unrelated models and expired evidence MUST remain eligible.

#### Scenario: Reused hard owner is excluded
- **WHEN** an HTTP continuation targets an existing bridge whose account/model pair is excluded
- **THEN** no new frame is sent to that account and ownership is preserved in the failure

#### Scenario: Movable request uses another account
- **WHEN** an unanchored HTTP request reuses a bridge with an excluded account/model pair
- **THEN** another eligible account can serve the request

#### Scenario: Exclusion arrives during admission
- **WHEN** exclusion is recorded while a bridge request waits for admission
- **THEN** that unsent request fails with its resources settled and accepted sibling turns remain able to complete
