## MODIFIED Requirements

### Requirement: Configurable subscription model Plan restriction

For a configured native model, selection SHALL intersect configured plans with existing eligibility gates and preserve ranking within that pool. Membership SHALL use normalized plan equality, not entitlement equivalences. A mapping SHALL NOT grant upstream entitlement or widen API-key scope. Unconfigured native models and model-source dispatch SHALL retain their existing behavior. An account reserved by the requesting API key is not excluded by the configured plans, subject to the owning-key exemption defined in "Reserved accounts are exclusive and preferred".

#### Scenario: Selected models use Free accounts

- **GIVEN** `gpt-5.6-terra`, `gpt-5.6-luna`, and `gpt-6-luna` are explicitly configured with `["free"]`
- **WHEN** a native request for a configured model is routed
- **THEN** only otherwise eligible Free accounts are candidates, plus, for a request with an API key, that key's reserved accounts that qualify for the owning-key exemption defined in "Reserved accounts are exclusive and preferred"
- **AND** the existing ranking strategy chooses among those candidates

#### Scenario: Restriction cannot grant access or widen scope

- **WHEN** a model is restricted to Free but Free lacks upstream entitlement or the API key permits only paid accounts
- **THEN** the restriction does not grant model access or select outside the key's account scope
- **AND** no account of another plan is selected, except an account reserved by the requesting key that qualifies for the owning-key exemption

#### Scenario: Plan equality is stricter than entitlement equivalence

- **WHEN** a model is restricted to `pro` and a candidate's normalized plan is `prolite`, unknown, or absent
- **THEN** that candidate fails the operator Plan restriction

#### Scenario: Unconfigured native models retain current behavior

- **GIVEN** a native model is absent from the mapping
- **WHEN** a request for that model is routed
- **THEN** existing selection applies without an additional operator Plan restriction
- **AND** final native dispatch adds no Plan or plan-check admission recheck for that model

#### Scenario: Source routing remains independent

- **GIVEN** a request resolves to a model source
- **WHEN** the subscription mapping contains the same or a similar model name
- **THEN** it does not modify source dispatch, eligibility, or source metadata

#### Scenario: Empty configured pool fails closed

- **GIVEN** a model is restricted to Free and no Free account passes existing eligibility gates
- **AND** the requesting key has no usable reserved account that qualifies for the owning-key exemption
- **WHEN** the request is routed
- **THEN** the existing routing error envelope is returned without paid fallback
- **AND** a single-account setting pointing at a paid account does not override the restriction, unless that account is reserved by the requesting key and qualifies for the owning-key exemption defined in "Reserved accounts are exclusive and preferred"

#### Scenario: Owning key uses its reserved account outside the configured plans

- **GIVEN** a model is restricted to Free, key K reserves `acc-r` on Plus, and a shared Free account and a shared Plus account exist
- **WHEN** a native request with key K for that model is routed and `acc-r` is usable
- **THEN** `acc-r` is selected
- **AND** when `acc-r` is unusable, only the shared Free account is a candidate

### Requirement: Plan restrictions preserve account ownership

Configured Plan restrictions SHALL apply to fresh selection and retries without changing owner discovery or sticky-mutation authority. The restriction SHALL NOT transfer account-pinned work or turn ambiguous ownership into a unique owner. Retry selection SHALL remain inside the configured eligible pool. A request that carries `previous_response_id` whose stored owner lookup missed SHALL NOT use the owning-key exemption defined in "Reserved accounts are exclusive and preferred" for any of its selections, replays, or dispatch admissions, on HTTP stream, compact and direct WebSocket; when no account remains, each transport keeps its existing error envelope.

#### Scenario: A pinned owner is outside the configured plans

- **GIVEN** a file or conversation pins a request to a paid account that is not reserved by the requesting key
- **AND** the requested native model is restricted to Free
- **WHEN** the request is routed
- **THEN** routing fails closed without selecting a different account

#### Scenario: Ownership ambiguity is unchanged

- **GIVEN** two accounts could own a conversation before policy filtering
- **WHEN** only one passes the configured Plan restriction
- **THEN** owner discovery remains ambiguous rather than assigning the surviving account

#### Scenario: Retry does not escape the configured pool

- **GIVEN** a Free-restricted native request encounters a retryable upstream error
- **WHEN** an eligible Free alternative and a paid alternative exist
- **THEN** retry may select only the Free alternative, or an account reserved by the requesting key that qualifies for the owning-key exemption, and retains existing replay and ownership limits

#### Scenario: Lookup-miss continuation keeps the configured pool

- **GIVEN** a model is restricted to Free, key K reserves `acc-r` on Plus and a shared Free `acc-s` exists
- **WHEN** a request with key K carries a `previous_response_id` whose owner lookup missed
- **THEN** the request is served by `acc-s`, including after a replay of the same request or a token refresh that changes a plan
- **AND** a fresh request with key K still selects `acc-r`

### Requirement: Plan restrictions participate in settings propagation

Selection caches SHALL distinguish effective model Plan mappings and follow existing settings invalidation and expiry. Fresh selection and reused-connection admission SHALL enforce the effective mapping and current persisted account plan rather than relying solely on cached selection or socket-open account snapshots. Admission SHALL read the account's current reservation together with its plan, so a released reservation stops the owning-key exemption defined in "Reserved accounts are exclusive and preferred" at the next admission check.

#### Scenario: Policy update and clearing with selection caching enabled

- **GIVEN** a paid selection is cached with a nonzero selection-cache TTL
- **WHEN** a Free restriction becomes effective through settings invalidation or expiry
- **THEN** subsequent selection excludes shared paid accounts, including one held in the cached selection
- **AND** a paid account still reserved by the requesting key remains selectable under the owning-key exemption
- **AND** clearing the restriction restores ordinary selection without reusing a policy-incompatible cached result

#### Scenario: Peer settings change becomes effective

- **WHEN** a peer's saved mapping becomes visible through the existing settings propagation mechanism
- **THEN** subsequent selection and warm admission enforce that mapping

#### Scenario: Persisted plan changes while a snapshot is stale

- **GIVEN** a cached selection or warm connection holds an allowed account-plan snapshot
- **WHEN** the persisted account plan no longer satisfies the effective mapping
- **THEN** new work cannot dispatch on that account using the stale plan

### Requirement: Final policy admission preserves accepted work

Native HTTP sends and same-account retries, and reusable bridge and WebSocket connections, SHALL enforce effective Plan restrictions after waits and before dispatch. Rejection SHALL settle the unsent request's reservation and admission resources without interrupting accepted siblings. On a session with an API key, HTTP bridge prewarm and replay sends (pre-created, authentication and security-work replays) SHALL recheck the effective restriction for the frame's own model and the session's API key after their waits, reading the reservation from the current account row and SHALL NOT send for a request whose consumer detached or whose deadline passed, releasing only resources the request still owns. Any retirement or reselection SHALL retain existing task, transport, and hard-owner lifecycle rules.

#### Scenario: Native HTTP admission and same-account retries

- **GIVEN** a native streaming or compact request selected an eligible account
- **WHEN** the effective policy or persisted account plan becomes incompatible during an admission wait or retry backoff
- **THEN** the unsent request cannot dispatch or retry on that account
- **AND** rejection releases its admission resources and reservation without an upstream health penalty or ownership transfer

#### Scenario: Policy changes during admission

- **GIVEN** a paid bridge or WebSocket has accepted work and another turn is waiting
- **WHEN** an effective policy update restricts that turn to Free
- **THEN** the unsent turn cannot dispatch on the paid socket, unless the socket's account is reserved by the turn's API key and qualifies for the owning-key exemption defined in "Reserved accounts are exclusive and preferred"
- **AND** accepted siblings retain reader, cleanup, and settlement ownership
- **AND** the unsent turn releases its admission resources and reservation

#### Scenario: Idle connection becomes policy-ineligible

- **WHEN** a movable new turn encounters an idle connection outside its configured plans whose account does not qualify for the owning-key exemption
- **THEN** it can re-enter eligible selection through the existing safe lifecycle
- **AND** a hard owner outside the restriction still fails closed without ownership transfer

### Requirement: Plan-restricted models drop a service tier no allowed Plan offers

For a native model configured in `modelPlanRoutingPolicies`, the configured Plans alone SHALL decide whether the tier is dropped; the owning-key exemption decides only which account may serve the request. The proxy SHALL remove a non-default service tier from the effective request before account selection and upstream forwarding when an authoritative account catalog recognizes the model and no allowed Plan offers that tier. This SHALL apply to client-requested and API-key-enforced tiers alike, and SHALL take precedence over the tier-forwarding promises of other capabilities for that model.

#### Scenario: Fast request on a Free-only model is served at the default tier

- **GIVEN** `gpt-6-luna` is configured with `["free"]`
- **AND** the authoritative catalog advertises `priority` for `gpt-6-luna` only on Plus accounts
- **WHEN** a native request for `gpt-6-luna` asks for `service_tier: "priority"` or the `fast` alias
- **THEN** an otherwise eligible Free account is selected, or an account reserved by the requesting key that qualifies for the owning-key exemption defined in "Reserved accounts are exclusive and preferred"
- **AND** the upstream payload omits `service_tier`

#### Scenario: An API-key-enforced tier is also dropped for a configured model

- **GIVEN** an API key enforces `priority` or `ultrafast`
- **AND** the requested model is configured with Plans that do not offer that tier
- **WHEN** the request is routed
- **THEN** the effective request omits `service_tier`
- **AND** it is routed within the configured Plans, or to an account reserved by the requesting key that qualifies for the owning-key exemption

#### Scenario: The tier fallback ignores the owning-key exemption

- **GIVEN** `gpt-6-luna` is configured with `["free"]` and the catalog offers `priority` only on Plus
- **AND** key K reserves a Plus account
- **WHEN** a request with key K asks for `priority`
- **THEN** the service tier is still dropped and K's Plus account may be selected

### Requirement: Reserved accounts are exclusive and preferred

An account reserved by an API key MUST NOT be selected for a request authenticated with another API key, nor for a keyless request, on any account-selection path: fresh selection, continuity owners, sticky reallocation, opportunistic admission, compact and stream retry, and codex control. A request whose required continuity owner is reserved by another key MUST fail closed with `continuity_owner_policy_conflict` instead of moving to another account. Replica-local runtime state of a reserved account (cooldown, backoff, health) MUST NOT be reset by traffic of other keys. A request authenticated with the owning key MUST select one of its usable reserved accounts before any other account in its pool, including when the reserved account is draining or above its budget threshold. When none of its reserved accounts is usable (quota exhausted, cooling down, paused or deactivated) it MUST fall back to its normal pool selection. When the routing strategy is `single_account`, the operator-pinned account MUST win over the preference while exclusivity still applies. For a request authenticated with the owning key, a reserved account of that key MUST NOT be excluded by the operator subscription model Plan restriction (`modelPlanRoutingPolicies`); this is the owning-key exemption. It MUST be decided from the reservation read in the same selection load or admission read, MUST NOT bypass catalog entitlement, quota, scope or other gates, and requests from other keys or keyless requests MUST receive exactly the result they receive without it. When no account is reserved, account selection MUST be unchanged.

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

#### Scenario: Other keys keep the restricted result

- **GIVEN** a model is restricted to Free and key K reserves Plus `acc-r`
- **WHEN** a request with key J or a keyless request for that model is routed
- **THEN** `acc-r` is not selected and the account, error code and message equal the result without the exemption
