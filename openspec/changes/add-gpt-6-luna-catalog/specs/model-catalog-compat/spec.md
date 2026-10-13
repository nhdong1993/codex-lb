## ADDED Requirements

### Requirement: GPT-6 Luna bootstrap metadata is available before refresh

The bootstrap catalog SHALL include native `gpt-6-luna` with the endpoint context, client, reasoning, tool, and plan metadata specified below. Its default service tier SHALL be unset while Fast remains available. Account eligibility SHALL accept advertised plans with case and surrounding whitespace normalized. The entry SHALL NOT be synthesized from a source model.

#### Scenario: Cold-start Codex-client catalogs expose GPT-6 Luna

- **GIVEN** no refreshed or persisted model-registry snapshot exists
- **WHEN** a client requests `GET /backend-api/codex/models` or `GET /v1/models?client_version=0.155.0`
- **THEN** the response contains `gpt-6-luna`
- **AND** its context window is 272000 and maximum context window is 872000
- **AND** its minimum client version is `0.155.0`
- **AND** it advertises websocket preference, Responses Lite, and code mode tools
- **AND** its default reasoning level is `medium`, with `low`, `medium`, `high`, `xhigh`, and `max` supported
- **AND** its available plans are the 26 endpoint labels: `business`, `edu`, `edu_plus`, `edu_pro`, `education`, `ent26`, `enterprise`, `enterprise_cbp_automation`, `enterprise_cbp_trial`, `enterprise_cbp_usage_based`, `finserv`, `free`, `free_workspace`, `go`, `hc`, `k12`, `law`, `plus`, `pro`, `prolite`, `promax`, `quorum`, `sci`, `self_serve_business_prolite`, `self_serve_business_usage_based`, `team`
- **AND** `default_service_tier` is `null` and `service_tiers` includes Fast (`priority`)

#### Scenario: Cold-start OpenAI-compatible catalog exposes supported GPT-6 Luna metadata

- **GIVEN** no refreshed or persisted model-registry snapshot exists
- **WHEN** a client requests `GET /v1/models` without `client_version`
- **THEN** the OpenAI-compatible `data` list contains an entry with `id` equal to `gpt-6-luna`
- **AND** its metadata reports context and input context windows of 272000, minimum client version `0.155.0`, websocket preference, and default reasoning level `medium`
- **AND** its metadata omits `default_service_tier` and includes Fast (`priority`) in `service_tiers`

#### Scenario: Endpoint-supported account plans remain eligible before refresh

- **GIVEN** no refreshed or persisted model-registry snapshot exists
- **AND** an account has any of the 26 advertised plans, including case and surrounding-whitespace variants
- **WHEN** account eligibility is evaluated for `gpt-6-luna`
- **THEN** bootstrap plan restrictions do not exclude that account

#### Scenario: Source models remain separate

- **GIVEN** an OpenAI-compatible source exposes a model with a similar name
- **WHEN** the Codex subscription bootstrap catalog is built
- **THEN** `gpt-6-luna` remains the subscription entry
- **AND** source-model routing metadata is not attached to it
