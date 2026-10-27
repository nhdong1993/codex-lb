## ADDED Requirements

### Requirement: Lifetime API key limits

API key limit rules MUST accept the `lifetime` limit window for every limit type. A lifetime limit MUST accumulate usage without any automatic reset: neither the lazy on-read reset nor the hourly fallback sweep may reset its `current_value`. A lifetime limit's `reset_at` MUST be later than any reachable current time and MUST change whenever its usage is reset, so reservations taken before a reset cannot settle into the reset counter. When a lifetime limit is added without `resetUsage`, its `current_value` MUST be initialized from all of the API key's retained successful request-log usage. A request rejected by an exceeded lifetime limit MUST return `429 rate_limit_exceeded` with a message stating that usage does not reset automatically and without a reset time.

#### Scenario: Create a lifetime limit

- **WHEN** admin submits `POST /api/api-keys/` with a limit `{ "limitType": "cost_usd", "limitWindow": "lifetime", "maxValue": 50000000 }`
- **THEN** the response contains that limit with `limitWindow: "lifetime"`

#### Scenario: Lifetime usage survives the reset sweep

- **GIVEN** an API key has a lifetime limit with `current_value` 900
- **WHEN** the hourly fallback sweep runs ten years later
- **THEN** the lifetime limit keeps `current_value` 900

#### Scenario: Adding a lifetime limit backfills all history

- **GIVEN** an API key has successful request-log usage from 400 days ago and from 1 hour ago, and failed usage from 30 days ago
- **WHEN** admin adds a lifetime `total_tokens` limit without `resetUsage`
- **THEN** the limit's `current_value` equals the sum of both successful rows and excludes the failed row

#### Scenario: Exceeded lifetime limit reports no reset time

- **GIVEN** an API key's lifetime limit is exhausted
- **WHEN** a proxied request uses that key
- **THEN** the response is `429 rate_limit_exceeded`
- **AND** the message says usage does not reset automatically and contains no reset timestamp

#### Scenario: Explicit reset clears a lifetime limit

- **GIVEN** an API key has a lifetime limit with non-zero usage
- **WHEN** admin submits `PATCH /api/api-keys/{id}` with `resetUsage: true`
- **THEN** the lifetime limit's `current_value` is 0
- **AND** its `reset_at` differs from the value before the reset

### Requirement: Dashboard API key usage reset

The dashboard API key edit dialog MUST offer a `Reset usage` action when the key has at least one limit. The action MUST ask for confirmation and, only after confirmation, MUST submit `PATCH /api/api-keys/{id}` with `resetUsage: true` and no other fields. The limit window selector MUST offer the lifetime window.

#### Scenario: Reset usage requires confirmation

- **GIVEN** the edit dialog is open for a key with limits
- **WHEN** the operator clicks `Reset usage`
- **THEN** a confirmation dialog appears and no update is sent
- **WHEN** the operator confirms
- **THEN** the dashboard sends `{ "resetUsage": true }` for that key

#### Scenario: No reset action without limits

- **GIVEN** the edit dialog is open for a key without limits
- **THEN** no `Reset usage` action is shown
