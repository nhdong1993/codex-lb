## ADDED Requirements

### Requirement: Plan-restricted models drop a service tier no allowed Plan offers

For a native model configured in `modelPlanRoutingPolicies`, the proxy SHALL remove a non-default service tier from the effective request before account selection and upstream forwarding when an authoritative account catalog recognizes the model and no allowed Plan offers that tier. This SHALL apply to client-requested and API-key-enforced tiers alike, and SHALL take precedence over the tier-forwarding promises of other capabilities for that model.

#### Scenario: Fast request on a Free-only model is served at the default tier

- **GIVEN** `gpt-6-luna` is configured with `["free"]`
- **AND** the authoritative catalog advertises `priority` for `gpt-6-luna` only on Plus accounts
- **WHEN** a native request for `gpt-6-luna` asks for `service_tier: "priority"` or the `fast` alias
- **THEN** an otherwise eligible Free account is selected
- **AND** the upstream payload omits `service_tier`

#### Scenario: An API-key-enforced tier is also dropped for a configured model

- **GIVEN** an API key enforces `priority` or `ultrafast`
- **AND** the requested model is configured with Plans that do not offer that tier
- **WHEN** the request is routed
- **THEN** the effective request omits `service_tier` and is routed within the configured Plans

### Requirement: The Plan-restricted tier fallback needs positive catalog evidence

The fallback SHALL be decided from Plan capability, not current account availability. It SHALL keep the requested tier when any allowed Plan offers it, when the model is not configured, when no authoritative catalog snapshot exists, when the catalog does not recognize the model, or when the routing policy cannot be read.

#### Scenario: An allowed Plan offers the tier

- **GIVEN** a model is configured with `["free", "plus"]` and Plus advertises `priority`
- **WHEN** a request asks for `service_tier: "priority"`
- **THEN** the tier is kept and selection considers only accounts that offer it
- **AND** the tier is kept even when no such account is currently available

#### Scenario: Unconfigured models keep explicit tiers

- **GIVEN** a native model is absent from the mapping
- **WHEN** a client explicitly asks for a tier no account offers for that model
- **THEN** the tier is not removed and the existing selection outcome applies

#### Scenario: Missing evidence keeps the tier

- **GIVEN** a model is configured
- **WHEN** the catalog snapshot is absent or not authoritative, the model is unknown to it, or the policy lookup fails
- **THEN** the requested tier is kept and existing routing, including fail-closed policy errors, applies

### Requirement: The Plan-restricted tier fallback leaves source and forwarded routing unchanged

The fallback SHALL apply only to subscription-account routes after model-source dispatch. A request served by a model source SHALL keep its tier even when its slug matches a configured native model. An owner-forwarded request SHALL keep the effective tier signed by its origin instance.

#### Scenario: Same-slug source request keeps its tier

- **GIVEN** a model source serves `gpt-6-luna` and the native `gpt-6-luna` is configured with `["free"]`
- **WHEN** a request routed to the source asks for `service_tier: "priority"`
- **THEN** the source request carries `service_tier: "priority"`

#### Scenario: Owner-forwarded request keeps the origin's tier

- **WHEN** an internal owner-forwarded request reaches the owning instance
- **THEN** that instance does not re-evaluate the fallback and forwards the tier it received
