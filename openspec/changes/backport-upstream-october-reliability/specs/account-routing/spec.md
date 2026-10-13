## ADDED Requirements

### Requirement: Code-less usage-limit terminals use shared classification

The proxy MUST recognize an upstream-authored usage-limit message on a normalized `upstream_error` envelope as a rate-limit rejection, whether delivered as an HTTP error body or an HTTP-stream/WebSocket terminal frame. Matching MUST normalize punctuation, case, and whitespace, including "usage limit has been reached". An explicit `usage_limit_reached` code MUST remain sufficient. Other explicit codes, including `invalid_request_error` and ordinary throttling, MUST retain their existing classification even when messages quote usage-limit wording.

HTTP-stream retry, account-health, and refresh decisions MUST use this shared recognition. The final exhausted account and a failure after visible output MUST still receive the appropriate health update without replaying visible output. WebSocket retry classification MUST use the existing `usage_limit_reached` internal path, preserving hard ownership, file affinity, and accepted-turn replay restrictions. API-key reservations MUST settle before deferred error-health writes. Recognition MUST NOT rewrite an error envelope delivered to the client or treat proven quota exhaustion as the short code-less-429 burst cooldown; the existing continuity rewrite of an owner-pinned `previous_response_id` failure applies to the code-less form exactly as to the coded form.

#### Scenario: Code-less HTTP terminal retries only before visibility
- **WHEN** a selected account emits a code-less usage-limit terminal before visible output and an eligible sibling is available
- **THEN** the ordinary retry path uses the sibling and records the exhausted account as rate limited
- **AND** hard owner and file pin restrictions remain in force

#### Scenario: Final or committed failure still records health
- **WHEN** a code-less usage-limit terminal arrives on the last account or after visible output
- **THEN** the error is surfaced unchanged and the exhausted account's health is recorded
- **AND** visible output is not replayed and keyed settlement precedes deferred health writes

#### Scenario: WebSocket quota recognition respects ownership
- **WHEN** a WebSocket terminal carries usage-limit wording without an explicit error code
- **THEN** quota classification and socket retirement use the same path as coded exhaustion
- **AND** existing owner-pinned and accepted-turn restrictions decide whether replay is allowed

#### Scenario: Owner-pinned code-less terminal matches the coded form
- **WHEN** an HTTP stream pinned to its `previous_response_id` owner receives a code-less usage-limit terminal before visible output
- **THEN** the client receives the same `previous_response_owner_unavailable` continuity failure as for a coded `usage_limit_reached` terminal
- **AND** the request never moves to a sibling and the owner is recorded as rate limited

#### Scenario: Request-shaped and unrelated failures stay unchanged
- **WHEN** an explicit `invalid_request_error` quotes usage-limit wording or a code-less message does not assert usage exhaustion
- **THEN** message recognition does not introduce a quota penalty or a sibling retry

#### Scenario: Code-less quota is not a burst
- **WHEN** a code-less HTTP 429 proves usage exhaustion in its upstream message
- **THEN** it is classified as rate limited rather than entering the short replica-local burst cooldown
