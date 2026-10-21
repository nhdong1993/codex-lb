## MODIFIED Requirements

### Requirement: Request logs persist requested, actual, and billable service tiers separately
For Responses proxy traffic, the system MUST persist the operator-requested tier, the upstream-reported actual tier when available, and the effective billable tier used for pricing as separate request-log fields.

The legacy `fast` alias MUST be normalized to the canonical upstream value
`priority` before forwarding and before it is stored as the requested tier.
The upstream-reported `response.service_tier`, when present, remains the
authoritative actual tier even when it differs from the requested tier.
When the account-routing Plan-restricted service tier fallback removes the
tier, the requested tier recorded is the effective request's omitted tier.

#### Scenario: Upstream reports a downgraded actual tier
- **WHEN** a client sends a Responses request with `service_tier: "priority"`
- **AND** the upstream response later reports `service_tier: "default"`
- **THEN** the persisted request log entry records `requested_service_tier = "priority"`
- **AND** the persisted request log entry records `actual_service_tier = "default"`
- **AND** the persisted request log entry records billable `service_tier = "default"`

#### Scenario: Fast alias is logged as a priority request
- **WHEN** a client sends a Responses request with `service_tier: "fast"`
- **AND** the upstream response later reports `service_tier: "default"`
- **THEN** the persisted request log entry records `requested_service_tier = "priority"`
- **AND** the persisted request log entry records `actual_service_tier = "default"`
- **AND** the persisted request log entry records billable `service_tier = "default"`

#### Scenario: Upstream omits the actual tier
- **WHEN** a client sends a Responses request with `service_tier: "priority"`
- **AND** the upstream response omits `service_tier`
- **THEN** the persisted request log entry records `requested_service_tier = "priority"`
- **AND** the persisted request log entry records `actual_service_tier = null`
- **AND** the persisted request log entry records billable `service_tier = "priority"`

#### Scenario: Plan-restricted fallback removed the tier
- **GIVEN** the Plan-restricted service tier fallback removed `priority` from a request
- **WHEN** the request log entry is persisted
- **THEN** it records `requested_service_tier = null`
- **AND** a diagnostic log line records the removed tier

### Requirement: Responses routes preserve the Ultrafast service tier

Responses-compatible routes MUST accept the canonical `ultrafast` service tier and MUST forward it unchanged, except when the account-routing Plan-restricted service tier fallback removes it for a configured model whose allowed Plans do not offer it. When upstream reports the actual response tier, request logging MUST preserve `ultrafast` using the existing requested, actual, and billable tier contract.

#### Scenario: Explicit Ultrafast request is forwarded

- **WHEN** a client sends a Responses request with `service_tier: "ultrafast"`
- **AND** the requested model is not configured with Plans that lack `ultrafast`
- **THEN** the forwarded upstream payload contains `service_tier: "ultrafast"`

#### Scenario: Plan-restricted model drops an unoffered Ultrafast tier

- **GIVEN** the requested native model is configured with Plans that do not offer `ultrafast`
- **WHEN** a client sends a Responses request with `service_tier: "ultrafast"`
- **THEN** the forwarded upstream payload omits `service_tier`

#### Scenario: Upstream confirms Ultrafast processing

- **WHEN** upstream completes a request with `response.service_tier: "ultrafast"`
- **THEN** the actual and billable request-log tiers are `ultrafast`
