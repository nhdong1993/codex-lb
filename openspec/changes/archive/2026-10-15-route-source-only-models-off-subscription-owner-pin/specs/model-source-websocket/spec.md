## MODIFIED Requirements

### Requirement: Source WebSocket routes retain source authorization and payload semantics

Both `/v1/responses` and `/backend-api/codex/responses`, including explicit trailing-slash equivalents without redirect, SHALL support opted-in source requests. Routing MUST apply raw/enforced public-model policy, source assignments, per-source overrides and aliases before dispatch. It MUST preserve source HTTP reasoning/instruction/tool semantics and validate original and effective ownership references. Subscription-owned anchors, uploaded-file ownership, structural compaction exclusions and required-capability security rules MUST retain their precedence over source dispatch. Unless a structural subscription exclusion or required-capability security routing applies, which keep their precedence, a subscription-owned anchor for a source-only model MUST NOT route the turn to a subscription account and MUST yield `model_source_requires_http_transport` as defined in `responses-api-compat`. Lookup failure MUST fail closed before reservation or upstream dispatch.

Domain errors raised during shared preparation or source quota reservation MUST retain the existing WebSocket error status, type, code, message and supplied parameter. This contract MUST also apply when the eventual backend is subscription and when no model source is configured.

Shared source ownership preparation MUST preserve the existing HTTP error envelope on both Responses route families and their trailing-slash equivalents. An unavailable recorded source owner MUST return status 409 with type `server_error` and code `previous_response_owner_unavailable` when `previous_response_id` is present, or `model_source_owner_unavailable` for other owned references. This contract MUST apply regardless of the source's WebSocket capability; WebSocket adaptation MUST retain the same ownership-error envelope.

#### Scenario: A recorded source owner becomes unavailable
- **GIVEN** an HTTP source response published a response or output-item reference
- **WHEN** the source is disabled and the client continues using that reference over HTTP or WebSocket
- **THEN** the shared ownership check MUST retain the 409 `server_error` envelope and the reference-appropriate error code
- **AND** the rejected turn MUST NOT reserve quota, acquire source admission or reach any provider

#### Scenario: Shared preparation rejects key policy
- **WHEN** a create on either public WebSocket route or trailing-slash equivalent uses a revoked key or a forbidden model or reasoning effort
- **THEN** it MUST retain the established authentication or permission error type and any parameter such as `reasoning.effort`
- **AND** no rejected request reaches a provider or acquires quota

#### Scenario: Source quota is exhausted
- **WHEN** source quota reservation rejects an initial or subsequent create with a rate-limit domain error
- **THEN** its WebSocket error MUST retain status 429 and `rate_limit_error`, consistent with HTTP Responses
- **AND** the rejected turn MUST release admission without creating a reservation or sending an upstream request

#### Scenario: Source alias reaches the selected provider
- **WHEN** an authorized create requests a source alias over either public WS path
- **THEN** only its selected source receives its mapped upstream model and source credential
- **AND** the client and accounting retain the public model identity

#### Scenario: Overrides cannot bypass file ownership
- **WHEN** a source override introduces an account-scoped file reference
- **THEN** the request is rejected before source reservation or dispatch and is not redirected using stale pre-override state

#### Scenario: Failed source lookup does not select an account
- **WHEN** source routing or ownership lookup fails
- **THEN** the turn receives an error, no subscription/source attempt is made, and no quota reservation remains

#### Scenario: A turn inherits a required capability
- **WHEN** a create carries a session, turn, parent-task or previous-response alias with a durable required capability, including an alias introduced by its effective source payload
- **THEN** capability routing takes precedence before any source admission or reservation
- **AND** unavailable lineage lookup fails closed and no source receives the turn

#### Scenario: A reconnect carries a subscription-owned turn state
- **WHEN** a create carries an explicit turn-state alias owned by a subscription account under the exact API key, including without a previous response ID
- **THEN** the source path MUST preserve subscription ownership or fail closed before source admission
- **AND** conflicting or unavailable ownership lookup MUST NOT permit source dispatch, while an unregistered synthesized source placeholder MUST remain usable

#### Scenario: A subscription anchor cannot pin a source-only model
- **WHEN** a create for a source-only model (claimed by a source, with no model candidate in the subscription model registry) carries a subscription-owned previous-response or turn-state anchor
- **AND** no structural subscription exclusion or required-capability routing applies
- **THEN** the turn MUST receive the service-level `model_source_requires_http_transport` failure
- **AND** neither a subscription account nor the source receives the turn, and no usage reservation remains held

#### Scenario: An invalid first subscription create is corrected
- **WHEN** shared or subscription-specific payload validation rejects the first create before backend preparation succeeds
- **THEN** the socket remains available for a corrected create without becoming bound to either backend
