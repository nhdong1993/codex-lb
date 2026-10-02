## ADDED Requirements

### Requirement: Cached model exclusion applies to the actual required owner

HTTP bridge reuse MUST reject a model-excluded cached or in-flight session as an unavailable required owner only when that session matches the request's required account. A request requiring a different healthy file owner MUST remain eligible to select that owner. Existing conversation and file ownership constraints MUST remain enforced.

#### Scenario: Healthy file owner differs from excluded cached account
- **WHEN** a cache key maps to model-excluded account A and a request using that key requires a file owned by healthy account B
- **THEN** both supported HTTP response routes select B and can complete the request
- **AND** accepted work on A is not interrupted

#### Scenario: In-flight creation resolves to a different account
- **WHEN** a file request waits for session creation that resolves to an excluded account different from its required file owner
- **THEN** the request can select its required healthy owner instead of reporting that owner unavailable

### Requirement: Bridge model-evidence read failures are local admission failures

A database failure while reading model-exclusion evidence before dispatch MUST return a sanitized retryable HTTP 503 error with code `upstream_unavailable`. The failing request MUST release its admission resources and API-key reservation. It MUST NOT send upstream, penalize account health, or close a transport serving accepted sibling requests. Cancellation MUST continue to propagate through existing cleanup.

#### Scenario: Evidence database fails after admission
- **WHEN** a new request has acquired bridge admission but its final model-evidence read fails while an accepted sibling is running
- **THEN** the new request returns the sanitized admission error without SQL or driver details
- **AND** its resources are released and the sibling completes normally without an account-health write

#### Scenario: Evidence database fails during cache lookup
- **WHEN** model-exclusion lookup fails before session reuse or creation
- **THEN** the request returns the same sanitized retryable error and sends no upstream request
