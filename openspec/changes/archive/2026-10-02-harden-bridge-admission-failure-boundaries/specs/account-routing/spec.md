## ADDED Requirements

### Requirement: Model-evidence lookup failures remain isolated across driver boundaries

Any failure of the HTTP bridge's pre-dispatch model-evidence lookup MUST produce the sanitized retryable `503 upstream_unavailable` admission error, including connection errors and timeouts not wrapped by SQLAlchemy. It MUST release only the unsent request's admission resources and reservation, preserve accepted sibling requests, and avoid account-health penalties. Cancellation MUST propagate through existing cancellation cleanup.

The same isolation MUST apply during initial account selection and direct WebSocket reuse/final admission. A direct WebSocket lookup failure MUST emit a sanitized terminal error for the unsent turn and preserve the socket and accepted siblings so a later turn can retry.

#### Scenario: Driver connection failure at final admission
- **WHEN** the database driver raises an unwrapped connection or timeout error during final model-evidence lookup while a sibling is accepted
- **THEN** the unsent request receives a sanitized 503 on either HTTP response route
- **AND** the sibling completes normally without a health penalty or premature transport closure

#### Scenario: Driver connection failure during reuse lookup
- **WHEN** the database driver raises before cached-session reuse
- **THEN** the request receives the same sanitized admission error without sending upstream

#### Scenario: Cold bridge lookup fails during account selection
- **WHEN** no bridge session is cached and account selection cannot read model-exclusion evidence
- **THEN** either HTTP route returns the sanitized 503 and sends no request upstream

#### Scenario: Direct WebSocket lookup fails with an accepted sibling
- **WHEN** reused-socket or final model admission fails on either WebSocket route
- **THEN** only the unsent turn receives `upstream_unavailable`, its reservation/gates are released, and the accepted sibling completes without health penalties
- **AND** the same downstream socket can accept a later turn after the database recovers

#### Scenario: Initial WebSocket selection cannot read model evidence
- **WHEN** the real account selector fails to read model evidence for a new WebSocket connection on either response route
- **THEN** it emits a sanitized `upstream_unavailable` error, settles the unsent request and sends nothing upstream
- **AND** the downstream socket remains available for a subsequent turn after recovery

### Requirement: Model exclusion preserves guarded goal restart selection

For a classified account-neutral goal restart, cached or in-flight owner model exclusion MUST NOT prevent the existing guarded account-selection path from evaluating replacement. Model exclusion alone MUST NOT authorize abandonment of a legacy owner. Requests with file, conversation, previous-response or unresolved tool dependencies MUST retain existing ownership restrictions.

#### Scenario: Excluded unavailable legacy owner on a live bridge
- **WHEN** a classified self-contained goal restart encounters a live legacy owner that is both quota-exceeded and model-excluded
- **THEN** guarded selection may select an eligible replacement and the admitted predecessor request completes before retirement

#### Scenario: Excluded unavailable owner after waiting for creation
- **WHEN** the same restart waits for an in-flight session whose owner is model-excluded
- **THEN** it still reaches guarded selection for a replacement

#### Scenario: Model rejection is the only unavailability evidence
- **WHEN** a restart's legacy owner is active but model-excluded
- **THEN** the model rejection alone cannot authorize abandonment or transfer of the legacy mapping

#### Scenario: Restart-shaped request carries account dependencies
- **WHEN** a restart-shaped request includes a file or previous-response dependency on an excluded owner
- **THEN** it remains bound to that owner and fails closed
