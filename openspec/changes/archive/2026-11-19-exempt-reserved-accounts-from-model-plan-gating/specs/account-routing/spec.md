## MODIFIED Requirements

### Requirement: Relative availability routing

The proxy account selector SHALL support a `relative_availability` routing strategy. The strategy SHALL evaluate only accounts that have passed the existing eligibility, health-tier, model-plan (subject to the owning-key Plan exemption defined in "Reserved accounts are exclusive and preferred"), quota, cooldown, circuit-breaker, and budget-safety gates. Re-authentication-required accounts SHALL be treated as hard-blocked routing candidates, the same as paused and deactivated accounts. For each candidate, it SHALL compute a raw score from remaining secondary-window credits divided by seconds until the secondary-window reset, using bounded fallbacks for unknown or near-immediate reset times, and SHALL select from the highest weighted candidates according to the configured power and top-K cutoff.

#### Scenario: Soon-resetting usable credits are preferred
- **GIVEN** two healthy eligible accounts with equal remaining secondary credits
- **AND** one account's secondary window resets sooner
- **WHEN** account selection uses `relative_availability`
- **THEN** the sooner-resetting account receives the higher relative-availability score

#### Scenario: Relative availability preserves canonical gates
- **GIVEN** one account is paused, reauth-required, deactivated, rate-limited, quota-exceeded, cooling down, or outside the requested model plan without qualifying for the owning-key Plan exemption defined in "Reserved accounts are exclusive and preferred"
- **WHEN** account selection uses `relative_availability`
- **THEN** that account is not selected by the relative-availability strategy

### Requirement: Single-account routing
The proxy routing layer SHALL support a `single_account` routing strategy configured by `single_account_id`. When enabled, the proxy SHALL route only through the configured account if that account exists, is available, and matches the requested model-plan scope or qualifies for the owning-key Plan exemption defined in "Reserved accounts are exclusive and preferred". If the setting is missing, unavailable, or incompatible with the request, the proxy SHALL fail the request with a routing error instead of silently falling back to another account.

#### Scenario: Configured account serves matching traffic
- **GIVEN** `single_account` routing is enabled with a configured available account
- **AND** the account matches the requested model-plan scope
- **WHEN** the proxy selects an account
- **THEN** the configured account is selected

#### Scenario: Missing or unavailable selected account does not fall back
- **GIVEN** `single_account` routing is enabled
- **AND** the configured account is missing, unavailable, exhausted, or outside the requested model-plan scope without qualifying for the owning-key Plan exemption defined in "Reserved accounts are exclusive and preferred"
- **WHEN** the proxy selects an account
- **THEN** no alternate account is selected
- **AND** the request fails with a routing error

#### Scenario: Pinned reserved account serves its key outside the model Plan

- **GIVEN** `single_account` routing is pinned to `acc-a`, reserved by key K, whose Plan is not in the requested model's Plan set
- **AND** the model registry has no per-account catalog or service-tier evidence excluding `acc-a`
- **WHEN** a request with key K is routed
- **THEN** `acc-a` is selected

#### Scenario: Plan exemption never moves a pinned route

- **GIVEN** `single_account` routing is pinned to unreserved `acc-b`, which is outside the requested model Plan, and key K reserves `acc-a`
- **WHEN** a request with key K is routed
- **THEN** no alternate account is selected
- **AND** the request fails with a routing error

### Requirement: Reserved accounts are exclusive and preferred

An account reserved by an API key MUST NOT be selected for a request authenticated with another API key, nor for a keyless request, on any account-selection path: fresh selection, continuity owners, sticky reallocation, opportunistic admission, compact and stream retry, and codex control. A request whose required continuity owner is reserved by another key MUST fail closed with `continuity_owner_policy_conflict` instead of moving to another account. Replica-local runtime state of a reserved account (cooldown, backoff, health) MUST NOT be reset by traffic of other keys. A request authenticated with the owning key MUST select one of its usable reserved accounts before any other account in its pool, including when the reserved account is draining or above its budget threshold. When none of its reserved accounts is usable (quota exhausted, cooling down, paused or deactivated) it MUST fall back to its normal pool selection. When the routing strategy is `single_account`, the operator-pinned account MUST win over the preference while exclusivity still applies. For a request authenticated with the owning key, a reserved account of that key MUST NOT be excluded only because its Plan is outside the requested model's Plan set from the model registry, or outside a requested service tier's Plan set when that set is the model's Plan set (no tier-specific registry data); this is the owning-key Plan exemption. The exemption MUST apply only when the model has a non-empty registry Plan set (a suppressed or undiscovered model is not exempted), MUST be decided from the account's reservation as read in the same selection load, and MUST NOT apply when the account's own per-account model catalog is known and omits the model, when per-account or tier-specific registry data excludes the requested service tier, or when the requested service tier is `ultrafast`. Accounts that are not reserved by the requesting key MUST keep the model Plan filter, and requests from other keys or keyless requests MUST receive exactly the selection result and error code and message they would receive without the exemption. HTTP bridge session reuse MUST apply the same exemption based on the reserved accounts of the API key that authenticated the current request. When no account is reserved, account selection MUST be unchanged.

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

#### Scenario: Owner key uses its reserved account outside the model Plan

- **GIVEN** key K reserves `acc-a` on Plan `plus`, the requested model's registry Plan set is `{pro}`, and unreserved `acc-b` is on Plan `pro`
- **WHEN** a request with key K is routed
- **THEN** `acc-a` is selected

#### Scenario: Plan-exempt owner falls back to the Plan-filtered pool

- **GIVEN** key K reserves `acc-a` outside the requested model Plan and `acc-a` is cooling down
- **AND** unreserved `acc-b` is inside the Plan and unreserved `acc-c` is outside it
- **WHEN** a request with key K is routed
- **THEN** `acc-b` is selected and `acc-c` is never selected

#### Scenario: Other keys keep the unexempted result

- **GIVEN** key K reserves `acc-a` outside the requested model Plan and no unreserved account is inside the Plan
- **WHEN** a request with key J or a keyless request is routed
- **THEN** the request fails with `no_plan_support_for_model`, the same code and message as without the reservation

#### Scenario: Per-account evidence still excludes a reserved account

- **GIVEN** key K reserves `acc-a`, and the registry's per-account catalog for `acc-a` omits the requested model, or the request asks for `ultrafast`, or tier-specific registry data excludes `acc-a`'s Plan
- **WHEN** a request with key K is routed
- **THEN** `acc-a` is not selected through the Plan exemption

#### Scenario: A released reservation loses the exemption

- **GIVEN** key K reserved `acc-a`, which is outside the requested model Plan, and the reservation is removed
- **WHEN** a later request with key K is routed or reaches an HTTP bridge session bound to `acc-a`
- **THEN** `acc-a` is filtered by the model Plan like any unreserved account

#### Scenario: Upstream rejection of an exempt account uses the existing retry

- **GIVEN** `acc-a` is key K's only reserved account, was selected through the owning-key Plan exemption, and the upstream rejects the model on `acc-a` as unsupported for the account
- **AND** unreserved `acc-b` is the only other account inside the requested model Plan, and the upstream accepts it
- **WHEN** the request is retried by the existing account/model-rejection retry
- **THEN** `acc-a` is excluded and `acc-b` serves the request
- **AND** with several reserved accounts the retry selects again in the usual order (other reserved accounts first) within its existing single replay, so a pool account is not guaranteed
