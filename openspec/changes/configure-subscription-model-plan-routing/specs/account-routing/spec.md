## ADDED Requirements

### Requirement: Subscription model Plan settings

Dashboard settings SHALL persist `modelPlanRoutingPolicies` as an exact subscription-model-to-plan-list mapping, defaulting to `{}`. Omission or null in a PUT SHALL preserve the mapping; `{}` SHALL clear it. Updates SHALL use existing settings authorization, optimistic versioning, audit, and invalidation contracts.

#### Scenario: Default and partial updates

- **WHEN** an installation upgrades or creates its settings row
- **THEN** its model Plan mapping is empty without seeding model-specific restrictions
- **AND** saving a mapping followed by an unrelated update or a null mapping preserves the saved mapping
- **AND** an explicit empty mapping removes all operator Plan restrictions

#### Scenario: Versioned and authorized updates

- **WHEN** an operator saves a mapping with the current `expectedVersion`
- **THEN** settings return the persisted mapping and an advanced version and audit its changed field
- **AND** a stale version returns 409 without replacing that mapping
- **AND** a guest cannot change the mapping

#### Scenario: Migration round trip

- **GIVEN** an existing settings row at the migration's parent revision
- **WHEN** the schema upgrades to the model Plan revision
- **THEN** the mapping is non-null and empty and unrelated settings are preserved
- **AND** rerunning the upgrade does not overwrite an operator's saved mapping
- **AND** downgrading and re-upgrading removes and recreates only the new field with an empty default

#### Scenario: Invalid stored mapping remains repairable

- **GIVEN** the stored mapping is invalid, for example after a manual edit or after a saved plan stops being recognized
- **WHEN** an operator reads settings
- **THEN** settings return only the stored entries that are still valid instead of failing
- **AND** native routing still fails closed until a settings update replaces the mapping
- **AND** a PUT with a valid mapping, including `{}`, replaces the invalid stored value

### Requirement: Strict subscription Plan configuration

The settings API SHALL accept exact nonblank model IDs without whitespace, including IDs absent from the catalog. Plan lists SHALL be nonempty and contain only recognized account-plan strings. Plans SHALL be normalized and deduplicated; invalid updates SHALL be rejected without partially changing settings.

#### Scenario: Normalize plans without rewriting model identity

- **WHEN** an operator saves a catalog-missing exact model ID with plans `[' PRO ', 'pro', 'prolite']`
- **THEN** the same model ID is persisted with `['pro', 'prolite']`
- **AND** different model case or suffix does not acquire the restriction

#### Scenario: Recognized operator plan vocabulary

- **WHEN** an operator configures an allowed plan
- **THEN** its normalized value is one of `free`, `plus`, `pro`, `prolite`, `team`, `business`, `enterprise`, or `edu`
- **AND** broader catalog entitlement labels do not expand this settings vocabulary

#### Scenario: Reject invalid configuration atomically

- **WHEN** a mapping contains a blank or whitespace-bearing model ID, an empty plan list, an unknown plan, or a non-string plan
- **THEN** the update fails validation and previously saved settings remain unchanged

### Requirement: Configurable subscription model Plan restriction

For a configured native model, selection SHALL intersect configured plans with existing eligibility gates and preserve ranking within that pool. Membership SHALL use normalized plan equality, not entitlement equivalences. A mapping SHALL NOT grant upstream entitlement or widen API-key scope. Unconfigured native models and model-source dispatch SHALL retain their existing behavior.

#### Scenario: Selected models use Free accounts

- **GIVEN** `gpt-5.6-terra`, `gpt-5.6-luna`, and `gpt-6-luna` are explicitly configured with `["free"]`
- **WHEN** a native request for a configured model is routed
- **THEN** only otherwise eligible Free accounts are candidates
- **AND** the existing ranking strategy chooses among those candidates

#### Scenario: Restriction cannot grant access or widen scope

- **WHEN** a model is restricted to Free but Free lacks upstream entitlement or the API key permits only paid accounts
- **THEN** the restriction does not grant model access or select outside the key's account scope
- **AND** no account of another plan is selected

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
- **WHEN** the request is routed
- **THEN** the existing routing error envelope is returned without paid fallback
- **AND** a single-account setting pointing at a paid account does not override the restriction

### Requirement: Plan restrictions preserve account ownership

Configured Plan restrictions SHALL apply to fresh selection and retries without changing owner discovery or sticky-mutation authority. The restriction SHALL NOT transfer account-pinned work or turn ambiguous ownership into a unique owner. Retry selection SHALL remain inside the configured eligible pool.

#### Scenario: A pinned owner is outside the configured plans

- **GIVEN** a file or conversation pins a request to a paid account
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
- **THEN** retry may select only the Free alternative and retains existing replay and ownership limits

### Requirement: Plan restrictions participate in settings propagation

Selection caches SHALL distinguish effective model Plan mappings and follow existing settings invalidation and expiry. Fresh selection and reused-connection admission SHALL enforce the effective mapping and current persisted account plan rather than relying solely on cached selection or socket-open account snapshots.

#### Scenario: Policy update and clearing with selection caching enabled

- **GIVEN** a paid selection is cached with a nonzero selection-cache TTL
- **WHEN** a Free restriction becomes effective through settings invalidation or expiry
- **THEN** subsequent selection excludes paid accounts
- **AND** clearing the restriction restores ordinary selection without reusing a policy-incompatible cached result

#### Scenario: Peer settings change becomes effective

- **WHEN** a peer's saved mapping becomes visible through the existing settings propagation mechanism
- **THEN** subsequent selection and warm admission enforce that mapping

#### Scenario: Persisted plan changes while a snapshot is stale

- **GIVEN** a cached selection or warm connection holds an allowed account-plan snapshot
- **WHEN** the persisted account plan no longer satisfies the effective mapping
- **THEN** new work cannot dispatch on that account using the stale plan

### Requirement: Policy evidence failures are local admission failures

Malformed persisted policy or unavailable policy evidence SHALL fail native admission closed with a sanitized `upstream_unavailable` error. Failure SHALL NOT dispatch upstream, expose database or driver details, or record upstream account-health failure. Cancellation SHALL retain its existing propagation and cleanup.

#### Scenario: Invalid or unavailable policy evidence

- **WHEN** native admission cannot read or validate its policy
- **THEN** HTTP admission returns the existing sanitized 503 envelope or WebSocket admission emits the corresponding request-local terminal error
- **AND** no native account receives the unsent request and no upstream health penalty is recorded

### Requirement: Final policy admission preserves accepted work

Native HTTP sends and same-account retries, and reusable bridge and WebSocket connections, SHALL enforce effective Plan restrictions after waits and before dispatch. Rejection SHALL settle the unsent request's reservation and admission resources without interrupting accepted siblings. Any retirement or reselection SHALL retain existing task, transport, and hard-owner lifecycle rules.

#### Scenario: Native HTTP admission and same-account retries

- **GIVEN** a native streaming or compact request selected an eligible account
- **WHEN** the effective policy or persisted account plan becomes incompatible during an admission wait or retry backoff
- **THEN** the unsent request cannot dispatch or retry on that account
- **AND** rejection releases its admission resources and reservation without an upstream health penalty or ownership transfer

#### Scenario: Policy changes during admission

- **GIVEN** a paid bridge or WebSocket has accepted work and another turn is waiting
- **WHEN** an effective policy update restricts that turn to Free
- **THEN** the unsent turn cannot dispatch on the paid socket
- **AND** accepted siblings retain reader, cleanup, and settlement ownership
- **AND** the unsent turn releases its admission resources and reservation

#### Scenario: Idle connection becomes policy-ineligible

- **WHEN** a movable new turn encounters an idle connection outside its configured plans
- **THEN** it can re-enter eligible selection through the existing safe lifecycle
- **AND** a hard owner outside the restriction still fails closed without ownership transfer

### Requirement: Dashboard subscription Plan editor

Routing settings SHALL provide an editor for native non-image models, retaining saved catalog-missing IDs for editing and removal. It SHALL prevent empty-plan saves and preserve complete mappings on unrelated settings saves. Controls SHALL remain busy during mutation and refetch. Localized copy SHALL explain that restrictions grant no upstream access and provide no fallback to another plan.

#### Scenario: Catalog and saved rows

- **WHEN** the editor loads a catalog containing native, source-only, and image-only entries and a saved ID absent from the catalog
- **THEN** its picker excludes unsaved source-only and image-only entries and includes saved IDs that are absent from the catalog or now listed only as source-only or image-only
- **AND** the operator can add, edit, or remove a saved restriction but cannot save zero plans

#### Scenario: Save conflict discards stale drafts

- **WHEN** a save conflicts with a newer settings version
- **THEN** refetch obtains the saved mapping and version before re-enabling controls
- **AND** stale drafts are reset so the next save uses the refreshed settings

#### Scenario: Ordinary save failure remains retryable

- **WHEN** saving fails without a settings-version conflict
- **THEN** the editor preserves the draft and displays the existing save error so the operator can retry

#### Scenario: Empty default and localized caution

- **WHEN** settings contain an empty mapping
- **THEN** the editor displays no configured restrictions, rather than seeding the three example models
- **AND** English, Korean, and Simplified Chinese explain the no-entitlement-grant and no-other-plan-fallback behavior
