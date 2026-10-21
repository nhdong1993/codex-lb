## MODIFIED Requirements

### Requirement: Preserve service_tier in Chat Completions mapping
When a Chat Completions request includes `service_tier`, the service MUST preserve that field when mapping the request to the internal Responses payload. For a subscription-account request, the account-routing Plan-restricted service tier fallback MAY then remove the tier before forwarding.

#### Scenario: Chat request includes fast-mode tier
- **WHEN** a client sends a valid Chat Completions request with `service_tier: "priority"`
- **THEN** the mapped Responses payload forwarded upstream includes `service_tier: "priority"`

#### Scenario: Plan-restricted model drops an unoffered tier
- **GIVEN** the requested native model is configured with Plans that do not offer `priority`
- **WHEN** a client sends a Chat Completions request with `service_tier: "priority"`
- **THEN** the Responses payload forwarded upstream omits `service_tier`
