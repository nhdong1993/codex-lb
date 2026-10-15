## MODIFIED Requirements

### Requirement: Authenticated Codex client setup

The Install tab SHALL offer macOS and Linux Bash scripts and a Windows PowerShell script to configure the shared Codex home used by Codex App, CLI, and IDE extension. It MUST offer script copying, installer file download, and a direct curl setup command. The UI MUST explain that setup configures already-installed clients, uses the current key, backs up and replaces existing configuration, authentication, and model catalog, and requires restarting clients. It MUST state that macOS/Linux setup requires Python 3. It MUST explain that WSL or remote extensions require setup in their own environment.

The system SHALL expose `GET /api/key-dashboard/install-script?platform=macos|linux|windows`, require an active unexpired Bearer API key regardless of global proxy authentication settings, and return only that caller's personalized text installer with no-store caching headers. The installer MUST use the dashboard origin's `/backend-api/codex` endpoint. It MUST export ordered model preferences: the enforced model when one is set, otherwise every allowed model in configured order, otherwise none. On each run it MUST skip preferences absent from the retained catalog and configure the first remaining preference; when no preference remains, including for unrestricted keys, it MUST configure the first retained catalog model. When preferences are skipped, setup MUST report the skipped names and the configured model on standard error without printing the credential. Unsupported platforms MUST be rejected. The script MUST NOT disclose account identities or other keys.

Generated scripts MUST configure `config.toml` and file-backed `auth.json` in `CODEX_HOME` when set, otherwise the user's `.codex` directory, and MUST back up existing files before replacing them. They MUST safely encode credential, endpoint, and model values as data rather than executable input, MUST NOT print the credential, and MUST restrict credential-file access to the current user. Failure to back up existing files MUST stop setup before replacement.

#### Scenario: Configure the current key on each supported platform

- **WHEN** an authenticated user selects macOS, Linux, or Windows in Install
- **THEN** copy and download actions export the platform-appropriate installer with the current key and endpoint
- **AND** the direct command fetches the same installer with Bearer authorization, without putting the key in the URL or executing a failed download
- **AND** visible previews mask the key and the UI warns that copied commands and files contain credentials

#### Scenario: Preserve recoverable existing configuration

- **GIVEN** existing Codex configuration and authentication files
- **WHEN** the user runs an installer successfully
- **THEN** the old files remain recoverable in a unique private backup directory
- **AND** the new files select codex-lb and authenticate with the exported key

#### Scenario: Skip preferred models missing from the catalog

- **GIVEN** a key allows `codex-auto-review`, `gpt-5.4-mini` and `gpt-5.6-luna` in that order
- **AND** its retained catalog lists `gpt-5.6-luna` but not the hidden or retired first two models
- **WHEN** an exported installer runs
- **THEN** setup succeeds and configures `gpt-5.6-luna`
- **AND** standard error names the skipped models and the configured model

#### Scenario: Fall back when no preferred model is cataloged

- **GIVEN** none of an exported installer's preferred models is in the retained catalog and the catalog is nonempty
- **WHEN** the installer runs
- **THEN** setup configures the first retained catalog model

#### Scenario: Reject invalid installer credentials

- **WHEN** a missing, invalid, inactive, or expired credential requests an installer
- **THEN** the endpoint returns 401 with no script
- **AND** a 401 in the Install tab clears the key-dashboard session without invoking administrator authentication

#### Scenario: Discard stale installer responses

- **WHEN** the platform changes, the user disconnects, or the Install tab unmounts during an installer fetch
- **THEN** a late response MUST NOT restore obsolete script or credential state

### Requirement: Installer refreshes the authorized native model catalog

Every execution of an exported installer MUST fetch `/api/key-dashboard/models` using only the exported codex-lb Bearer key, retain only list-visible API models, preserve their complete native metadata, and write `codex-lb-models.json` in the selected Codex home. The installer MUST configure `model_catalog_json` as the safely encoded absolute file path. It MUST NOT expose upstream credentials, source assignments, or server-side alias mappings.

The catalog endpoint MUST require an active unexpired Bearer API key regardless of global proxy authentication settings, reuse native catalog serialization and key/source scoping, and return private no-store responses without consuming inference limits.

For a key assigned model sources and no subscription accounts, the exported provider SHALL enable WebSockets only when its nonempty eligible Responses source set is entirely streaming and native-WebSocket capable and runtime/global policy permits source WebSocket. Otherwise that source-only provider MUST use HTTP Responses. Mixed, account-only and unassigned key providers SHALL retain WebSocket support. Export MUST determine this policy from authenticated assignments and capabilities without exposing them. The installer MUST back up and protect the catalog alongside configuration and authentication. Failed downloads, redirects, invalid or empty catalogs, unsafe target paths, and backup failures MUST stop setup before replacement and MUST NOT print the credential or response body.

Eligibility MUST be evaluated before streaming/WebSocket filtering. Eligibility MUST use the effective routed model after key model enforcement, alias resolution and fast-mode prohibition, while preserving exact source alias precedence, model permissions and source assignment scope. The provider WebSocket flag MUST be fixed at export. Re-running an existing export MUST refresh its catalog without changing that embedded flag; a new export MUST evaluate current assignment, capability and global transport policy.

An allowlisted name with no eligible enabled Responses source after effective model routing MUST NOT count as an incapable member of the installer aggregate. Eligible HTTP-only or nonstreaming Responses candidates MUST still disable WebSocket preference. If no eligible Responses candidate remains, including when an enforced model has none, a source-only installer MUST disable WebSockets.

#### Scenario: Allowlist includes a model outside Responses eligibility

- **GIVEN** a source-only key permits a nonempty native-capable Responses set and also a Chat-only, disabled or unassigned model
- **WHEN** a new installer is exported on any supported platform
- **THEN** names with no eligible Responses candidate MUST NOT disable WebSocket for that eligible set
- **AND** the native-capable models retain their catalog WebSocket preference

#### Scenario: Install custom aliases with agent metadata

- **GIVEN** a source-only key can access a streaming Responses source without native WebSocket support and with public alias `cd/gpt-6-astra`
- **WHEN** its installer runs successfully
- **THEN** the local catalog contains the public alias and its native instructions, tool capabilities, and agent metadata
- **AND** inaccessible, disabled, non-streaming, and hidden models are not installed
- **AND** the provider uses HTTP and credentials contain only the codex-lb key

#### Scenario: Install an opted-in source-only key

- **GIVEN** every eligible Responses source/model for a source-only key supports native WebSocket and runtime/global policy permits it
- **WHEN** a newly exported installer runs successfully
- **THEN** its provider supports WebSocket and its catalog preserves the verified model transport preferences
- **AND** no source identity or upstream secret is exported

#### Scenario: Refresh the catalog on repeat runs

- **GIVEN** an exported script and an existing local catalog
- **WHEN** the operator adds an allowed alias and the user reruns the same script
- **THEN** the newly fetched catalog replaces the previous one and includes the alias
- **AND** the previous catalog remains in the private backup directory

#### Scenario: Disable WebSockets for source-only assignments

- **GIVEN** a key has assigned model sources and no assigned accounts, and its eligible source/model set is not entirely native-WebSocket capable
- **WHEN** its installer is exported and run on any supported platform
- **THEN** the provider disables WebSockets even if the catalog includes native models or a source uses a native model slug

#### Scenario: Preserve WebSockets for mixed assignments

- **GIVEN** a key has both assigned accounts and assigned model sources
- **WHEN** its installer is exported and run
- **THEN** the provider enables WebSockets even if its model allowlist contains only source models preferring HTTP
- **AND** installed per-model transport preferences remain unchanged and unsupported source turns retain their HTTP-required error behavior

#### Scenario: Preserve WebSockets for account-only and unassigned keys

- **WHEN** a key with only assigned accounts or no explicit assignments exports and runs its installer
- **THEN** the provider enables WebSockets regardless of catalog preferences

#### Scenario: Refresh catalog without overriding exported assignment policy

- **GIVEN** an installer exported with a provider WebSocket flag
- **WHEN** catalog preferences, source capabilities or global transport policy change and the same script is rerun
- **THEN** the catalog refreshes while the exported provider flag remains unchanged
- **AND** exporting a new script uses current assignments, capabilities and global policy

#### Scenario: Capability changes require a new export

- **GIVEN** a source-only installer was exported with WebSocket disabled and the sources later become entirely capable
- **WHEN** the old installer is rerun
- **THEN** it refreshes the catalog but keeps its embedded WebSocket flag disabled
- **AND** a newly exported installer evaluates the current capability and can enable WebSocket

#### Scenario: Failed refresh preserves the client setup

- **WHEN** catalog download or validation fails, or a catalog target is a symlink or non-file
- **THEN** existing configuration, authentication and catalog files remain unchanged
- **AND** the script exits with an actionable error without printing credentials

#### Scenario: Optional proxy authentication does not bypass installer scope

- **GIVEN** global proxy authentication is disabled
- **WHEN** an installer downloads its catalog
- **THEN** the endpoint still validates the supplied key and scopes the catalog to its model/source policy
- **AND** missing, invalid, expired or inactive keys are rejected with 401
