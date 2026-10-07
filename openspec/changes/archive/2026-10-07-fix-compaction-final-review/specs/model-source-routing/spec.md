## ADDED Requirements

### Requirement: Compact terminal usage validation is fail-closed

For source-routed standalone compaction on an API key requiring usage for
settlement, a non-null usage payload supplied by the terminal
`response.completed` event at the nested response or, when nested usage is
absent or null, the event root MUST validate before it can be used for compact
output, request logging or quota settlement. A malformed or negative terminal payload MUST return the
existing `usage_unavailable` error even when an earlier stream event supplied
valid usage. A valid terminal payload MUST retain precedence. An absent or
null terminal payload MAY fall back to valid usage observed in earlier events.
Validation MUST reject negative input, output, total, cached or reasoning token
counters, including counters within usage detail objects.

#### Scenario: Malformed terminal root usage is not replaced

- **GIVEN** an API key requires usage for settlement
- **AND** an earlier SSE event reports valid usage
- **AND** the terminal event root reports a non-null malformed or negative
  usage object
- **WHEN** either standalone compact route completes
- **THEN** the proxy returns HTTP 502 with `usage_unavailable`
- **AND** it releases the reservation without returning compact output

#### Scenario: Negative detail counters fail closed

- **GIVEN** a limited API key and valid earlier SSE usage
- **AND** terminal usage contains valid input/output but negative total, cached
  or reasoning counters at either the event root or nested response
- **WHEN** either compact route completes
- **THEN** it returns `usage_unavailable` without quota charge or compact output

### Requirement: Compact source requests retain reasoning provenance

When request policy materializes a provider-facing reasoning effort for a
source-routed compact request, conversion to the source Responses request MUST
preserve that materialization provenance. Source payload shaping MUST remove
proxy-added reasoning effort when the policy does not require it, while
retaining client-provided reasoning controls and policy-required aliases.

#### Scenario: Provider alias survives compact conversion

- **GIVEN** a client supplies a provider reasoning alias without canonical effort
- **AND** the API key does not enforce or restrict reasoning effort
- **WHEN** either standalone compact route dispatches to its source
- **THEN** its reasoning controls match the equivalent terminal-trigger request
- **AND** no proxy-added canonical effort is sent to the provider

#### Scenario: Explicit or policy-required canonical effort is retained

- **WHEN** a compact request supplies explicit canonical reasoning effort or
  its API key requires canonical effort
- **THEN** source forwarding retains that effort under the existing policy
