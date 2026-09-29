## MODIFIED Requirements

### Requirement: Installer refreshes the authorized native model catalog

Every execution of an exported installer MUST fetch `/api/key-dashboard/models` using only the exported codex-lb Bearer key, retain only list-visible API models, preserve their complete native metadata, and write `codex-lb-models.json` in the selected Codex home. The installer MUST configure `model_catalog_json` as the safely encoded absolute file path. It MUST NOT expose upstream credentials, source assignments, or server-side alias mappings.

The catalog endpoint MUST require an active unexpired Bearer API key regardless of global proxy authentication settings, reuse native catalog serialization and key/source scoping, and return private no-store responses without consuming inference limits.

At script export, the provider MUST set `supports_websockets=false` if and only if the authenticated key has at least one assigned model source and no assigned accounts. Mixed account/source assignments, account-only assignments, and keys without explicit assignments MUST retain `supports_websockets=true`, regardless of catalog model preferences. The exported flag MUST remain unchanged during catalog refresh, and per-model `prefer_websockets` metadata MUST be preserved. The installer MUST back up and protect the catalog alongside configuration and authentication. Failed downloads, redirects, invalid or empty catalogs, unavailable selected models, unsafe target paths, and backup failures MUST stop setup before replacement and MUST NOT print the credential or response body.

#### Scenario: Install custom aliases with agent metadata

- **GIVEN** a key is assigned only a streaming Responses source with public alias `cd/gpt-6-astra`
- **WHEN** its installer runs successfully
- **THEN** the local catalog contains the public alias and its native instructions, tool capabilities, and agent metadata
- **AND** inaccessible, disabled, non-streaming, and hidden models are not installed
- **AND** the provider uses HTTP and credentials contain only the codex-lb key

#### Scenario: Refresh the catalog on repeat runs

- **GIVEN** an exported script and an existing local catalog
- **WHEN** the operator adds an allowed alias and the user reruns the same script
- **THEN** the newly fetched catalog replaces the previous one and includes the alias
- **AND** the previous catalog remains in the private backup directory

#### Scenario: Disable WebSockets for source-only assignments

- **GIVEN** a key has assigned model sources and no assigned accounts
- **WHEN** its installer is exported and run on any supported platform
- **THEN** the provider disables WebSockets even if the catalog includes native models or a source uses a native model slug

#### Scenario: Preserve WebSockets for mixed assignments

- **GIVEN** a key has both assigned accounts and assigned model sources
- **WHEN** its installer is exported and run
- **THEN** the provider enables WebSockets even if its model allowlist contains only source models preferring HTTP
- **AND** installed per-model transport preferences remain unchanged

#### Scenario: Preserve WebSockets for account-only and unassigned keys

- **WHEN** a key with only assigned accounts or no explicit assignments exports and runs its installer
- **THEN** the provider enables WebSockets regardless of catalog preferences

#### Scenario: Refresh catalog without overriding exported assignment policy

- **GIVEN** an installer exported with a provider WebSocket flag
- **WHEN** catalog preferences change and the same script is rerun
- **THEN** the catalog refreshes while the exported provider flag remains unchanged
- **AND** exporting a new script uses the key's current assignments

#### Scenario: Failed refresh preserves the client setup

- **WHEN** catalog download or validation fails, or a catalog target is a symlink or non-file
- **THEN** existing configuration, authentication and catalog files remain unchanged
- **AND** the script exits with an actionable error without printing credentials

#### Scenario: Optional proxy authentication does not bypass installer scope

- **GIVEN** global proxy authentication is disabled
- **WHEN** an installer downloads its catalog
- **THEN** the endpoint still validates the supplied key and scopes the catalog to its model/source policy
- **AND** missing, invalid, expired or inactive keys are rejected with 401
