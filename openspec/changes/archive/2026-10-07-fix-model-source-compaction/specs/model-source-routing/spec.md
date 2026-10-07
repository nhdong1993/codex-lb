## ADDED Requirements

### Requirement: Responses compaction follows the selected model-source owner

An enabled OpenAI-compatible source that serves the requested public Responses
model MUST remain eligible for Codex terminal `compaction_trigger` requests and
standalone compact requests. Selection MUST use the same raw/enforced model,
source assignment, enablement, alias, streaming capability and durable
ownership checks as an ordinary Responses request. The source's configured
credential and upstream model mapping MUST be used for the compact operation.

Recorded subscription ownership, uploaded-file ownership, conflicting retained state or unknown state in a pool, disabled sources/models, and a changed source
credential or revision MUST retain their existing precedence and MUST NOT fall
through silently to another credential.

#### Scenario: Codex terminal compaction stays on its Model Source

- **GIVEN** an enabled Responses-capable source owns public model `m`
- **WHEN** `/backend-api/codex/responses` for `m` ends its input with one
  terminal `compaction_trigger`
- **THEN** the request is forwarded to that source with its mapped upstream
  model and source credential
- **AND** no subscription account receives the request

#### Scenario: Standalone compact stays on its Model Source

- **GIVEN** an enabled Responses-capable source owns public model `m`
- **WHEN** `/backend-api/codex/responses/compact` or `/v1/responses/compact`
  is called for `m`
- **THEN** the source Responses endpoint receives the retained history and
  exactly one terminal `compaction_trigger`
- **AND** the client receives the existing compact JSON contract

#### Scenario: Subscription ownership still wins

- **GIVEN** a request carries retained state recorded for a subscription
  account
- **WHEN** a source also exposes the requested public model
- **THEN** compaction remains on the recorded subscription owner
- **AND** the source is not contacted

#### Scenario: Unavailable source ownership fails closed

- **WHEN** retained compaction state has a conflicting or unavailable source owner, or an unknown owner in a pool
- **THEN** the proxy returns the existing ownership error before source or
  subscription dispatch
- **AND** no usage reservation remains held

#### Scenario: Continuation crosses replicas after compact

- **WHEN** compact output from a source is replayed through another replica
- **THEN** its response, item and encrypted-content references resolve from the shared database to the same source revision
- **AND** a different local source selection order MUST NOT change that owner

#### Scenario: Trailing slash behavior remains compatible

- **WHEN** either standalone compact endpoint is requested with a trailing slash
- **THEN** it MUST retain the existing 405 rejection without dispatch or reservation
- **AND** both HTTP Responses trigger routes MUST retain their supported slash equivalents without redirect
