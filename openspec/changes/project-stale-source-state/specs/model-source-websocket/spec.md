## MODIFIED Requirements

### Requirement: Source ownership is durable before event delivery

All response, item, call, encrypted and hosted-resource references introduced by source output MUST be recorded before their containing event is delivered, within the exact client-key/public-model/source-revision scope. Conflicting, unavailable or invalidated owners MUST fail closed, except that a create on a fresh or reconnected source session whose only conflict is the same source's earlier credential, endpoint or upstream-model revision SHALL use the same-source stale-state projection defined by `model-source-routing`. Changing transport or HA replica MUST NOT authorize another source/credential. Publication failure MUST withhold the affected output, terminate the attempt and prohibit replay. Reconnection MUST NOT silently remove an anchor or reconstruct missing connection-local history.

#### Scenario: A reconnect reaches a different replica
- **WHEN** a continuation uses an ID delivered by a source on another replica
- **THEN** it resolves only to the recorded eligible owner
- **AND** missing upstream state returns a safe continuity error without cross-source retry

#### Scenario: A provider reports a stale response anchor
- **WHEN** the selected provider reports a recognized missing previous response after reconnect
- **THEN** the Codex-native route exposes sanitized `previous_response_not_found` and the public route exposes `stream_incomplete`
- **AND** neither envelope reveals the raw provider message, missing anchor or endpoint

#### Scenario: Ownership publication fails
- **WHEN** persistence fails before an output reference is delivered
- **THEN** that event is withheld, attempt cleanup completes and no other source receives a replay

#### Scenario: A reconnected session continues after source reconfiguration
- **GIVEN** a source's token, endpoint or upstream-model mapping changed after it served earlier turns of a conversation
- **WHEN** a socket bound to the earlier revision receives another create
- **THEN** that create MUST still receive the reconnect-required turn error and MUST NOT be forwarded
- **AND WHEN** the client reconnects and sends a create carrying the full input without `previous_response_id`
- **THEN** the source MUST receive the projected input defined by `model-source-routing`, and earlier-revision anchors MUST still fail closed
