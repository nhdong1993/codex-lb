## ADDED Requirements

### Requirement: API key reserved accounts

`POST /api/api-keys` and `PATCH /api/api-keys/{id}` MUST accept an optional `reservedAccountIds` list. Every API key read contract (create, update, get, list) MUST return `reservedAccountIds`, sorted. An account MUST be reserved by at most one API key. Ids MUST be normalized like `assignedAccountIds` (trimmed, blanks dropped, duplicates removed). A PATCH that omits `reservedAccountIds` MUST leave the reservations unchanged; `[]` MUST release every account the key reserves; a list MUST reserve exactly those accounts and release the key's other accounts. An unknown account id MUST return `400 invalid_api_key_payload`. An account already reserved by another API key MUST return `409 account_reserved_by_other_key`. On either error nothing in the request MUST be committed, including other fields of the same request. When the key has account-assignment scope enabled, its assigned accounts after the write MUST include every reserved account; a key without account-assignment scope MUST stay unscoped. Deleting an API key MUST release its reserved accounts.

#### Scenario: Create a key with reserved accounts

- **WHEN** admin submits `POST /api/api-keys` with `reservedAccountIds: ["acc-b", "acc-a"]`
- **THEN** the response contains `reservedAccountIds: ["acc-a", "acc-b"]`
- **AND** `GET /api/api-keys` returns the same list for that key

#### Scenario: Update releases dropped accounts

- **GIVEN** key K reserves `acc-a` and `acc-b`
- **WHEN** admin submits `PATCH /api/api-keys/{K}` with `reservedAccountIds: ["acc-b"]`
- **THEN** the response contains `reservedAccountIds: ["acc-b"]`
- **AND** another key can then reserve `acc-a`

#### Scenario: Account reserved by another key

- **GIVEN** key K reserves `acc-a`
- **WHEN** admin submits `PATCH /api/api-keys/{J}` with `{ "name": "renamed", "reservedAccountIds": ["acc-a"] }`
- **THEN** the response is `409` with error code `account_reserved_by_other_key`
- **AND** key J keeps its previous name
- **AND** `acc-a` stays reserved by K

#### Scenario: Unknown reserved account

- **WHEN** admin submits `PATCH /api/api-keys/{K}` with `reservedAccountIds: ["missing"]`
- **THEN** the response is `400` with error code `invalid_api_key_payload`

#### Scenario: Scoped key assignment includes reserved accounts

- **GIVEN** key K has account-assignment scope with `assignedAccountIds: ["acc-b"]`
- **WHEN** admin reserves `acc-a` for K
- **THEN** K returns `assignedAccountIds: ["acc-a", "acc-b"]`

#### Scenario: Unscoped key stays unscoped

- **GIVEN** key K has no account-assignment scope
- **WHEN** admin reserves `acc-a` for K
- **THEN** K returns `accountAssignmentScopeEnabled: false`

#### Scenario: Deleting the key releases its accounts

- **GIVEN** key K reserves `acc-a`
- **WHEN** admin deletes K
- **THEN** another key can reserve `acc-a`

### Requirement: Reset-credit and warmup honor reserved accounts

Reset-credit listing and redeem, `/v1` warmup and `POST /api/quota-planner/warm-now` with an API key MUST treat an account reserved by another API key as outside the caller's account pool. A keyless `/v1` warmup MUST skip every reserved account. A keyed `warm-now` on an account reserved by another key MUST be skipped with reason `account_reserved_by_other_key` before any usage reservation is taken. Scheduler-driven warmups without an API key are unchanged.

#### Scenario: Reset credits of another key's account are hidden

- **GIVEN** key K reserves `acc-a`
- **WHEN** key J lists reset credits
- **THEN** `acc-a` is not included
- **AND** key K's listing still includes `acc-a`

#### Scenario: Warmup skips another key's account

- **GIVEN** key K reserves `acc-a`
- **WHEN** key J calls `/v1` warmup
- **THEN** `acc-a` is not warmed

#### Scenario: Keyed warm-now on another key's account

- **GIVEN** key K reserves `acc-a`
- **WHEN** admin calls `warm-now` for `acc-a` with `apiKeyId` J
- **THEN** the decision is `skipped` with reason `account_reserved_by_other_key`
- **AND** no upstream request is sent

### Requirement: All-accounts automations skip reserved accounts

An automation job scoped to all accounts MUST NOT dispatch runs to accounts reserved by an API key. An automation job that names a reserved account explicitly MUST still dispatch to it.

#### Scenario: All-accounts job skips a reserved account

- **GIVEN** key K reserves `acc-a` and `acc-b` is unreserved
- **WHEN** an automation job with no selected accounts runs
- **THEN** the run cycle contains `acc-b` only

#### Scenario: Explicitly selected reserved account still runs

- **GIVEN** key K reserves `acc-a`
- **WHEN** an automation job that selects `acc-a` runs
- **THEN** the run cycle contains `acc-a`
