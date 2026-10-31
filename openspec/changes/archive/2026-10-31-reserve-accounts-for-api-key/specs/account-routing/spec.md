## ADDED Requirements

### Requirement: Reserved accounts are exclusive and preferred

An account reserved by an API key MUST NOT be selected for a request authenticated with another API key, nor for a keyless request, on any account-selection path: fresh selection, continuity owners, sticky reallocation, opportunistic admission, compact and stream retry, and codex control. A request whose required continuity owner is reserved by another key MUST fail closed with `continuity_owner_policy_conflict` instead of moving to another account. Replica-local runtime state of a reserved account (cooldown, backoff, health) MUST NOT be reset by traffic of other keys. A request authenticated with the owning key MUST select one of its usable reserved accounts before any other account in its pool, including when the reserved account is draining or above its budget threshold. When none of its reserved accounts is usable (quota exhausted, cooling down, paused or deactivated) it MUST fall back to its normal pool selection. When the routing strategy is `single_account`, the operator-pinned account MUST win over the preference while exclusivity still applies. When no account is reserved, account selection MUST be unchanged.

#### Scenario: Owner key prefers its reserved account

- **GIVEN** key K reserves `acc-a` at 80% usage and `acc-b` is unreserved at 5% usage
- **WHEN** a request with key K is routed
- **THEN** `acc-a` is selected

#### Scenario: Owner key falls back to the pool

- **GIVEN** key K reserves `acc-a`, which is quota exhausted, cooling down or paused
- **WHEN** a request with key K is routed
- **THEN** an unreserved account of K's pool is selected

#### Scenario: Other keys never use the reserved account

- **GIVEN** key K reserves `acc-a`, which has the lowest usage
- **WHEN** a request with key J is routed
- **THEN** `acc-a` is not selected

#### Scenario: Keyless requests never use reserved accounts

- **GIVEN** API key authentication is disabled and `acc-a` is reserved by key K
- **WHEN** a keyless request is routed
- **THEN** `acc-a` is not selected

#### Scenario: Continuity owner reserved by another key fails closed

- **GIVEN** a conversation of key J is owned by `acc-a`, which key K now reserves
- **WHEN** key J sends a request that requires that owner
- **THEN** the request fails with `continuity_owner_policy_conflict`
- **AND** no other account is selected

#### Scenario: Single-account routing wins over the preference

- **GIVEN** the routing strategy is `single_account` pinned to unreserved `acc-b`, and key K reserves `acc-a`
- **WHEN** a request with key K is routed
- **THEN** `acc-b` is selected
