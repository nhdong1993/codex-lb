## RENAMED Requirements

- FROM: `### Requirement: Astra Ultra advertises max reasoning effort`
- TO: `### Requirement: Selected subscription models advertise max for Ultra`

## MODIFIED Requirements

### Requirement: Selected subscription models advertise max for Ultra

The native Codex catalog, its `client_version` compatibility variant at `/v1/models`, and the authenticated installer catalog at `/api/key-dashboard/models` MUST advertise `multi_agent_reasoning_effort: "max"` for subscription `gpt-6-astra` and `gpt-6.1-sol` when the model advertises both `max` and `ultra` reasoning levels. This override MUST take precedence over an upstream value or its absence, without changing the model's default effort, supported effort list, other capability metadata, or stored upstream metadata. Other models, custom model sources, and entries missing either supported effort MUST retain their upstream multi-agent effort metadata. Explicit request efforts MUST retain their existing semantics.

#### Scenario: Astra Ultra uses max across client catalogs

- **GIVEN** subscription `gpt-6-astra` advertises `max` and `ultra`, with upstream multi-agent effort `xhigh`, `null`, or absent
- **WHEN** a client retrieves a native, versioned compatibility, or installer Codex catalog
- **THEN** Astra advertises `multi_agent_reasoning_effort: "max"`
- **AND** its default effort, supported efforts, other capabilities, and stored upstream metadata remain unchanged

#### Scenario: GPT-6.1 Sol Ultra uses max across client catalogs

- **GIVEN** subscription `gpt-6.1-sol` advertises `max` and `ultra`, with upstream multi-agent effort `xhigh`, `null`, or absent
- **WHEN** a client retrieves a native, versioned compatibility, or installer Codex catalog
- **THEN** GPT-6.1 Sol advertises `multi_agent_reasoning_effort: "max"`
- **AND** its default effort, supported efforts, other capabilities, and stored upstream metadata remain unchanged

#### Scenario: Preserve models outside the Astra Ultra policy

- **GIVEN** a different model, a custom source model, or an Astra or GPT-6.1 Sol entry lacking `max` or `ultra`
- **WHEN** a client retrieves a Codex catalog
- **THEN** the multi-agent effort remains the upstream value or remains absent
