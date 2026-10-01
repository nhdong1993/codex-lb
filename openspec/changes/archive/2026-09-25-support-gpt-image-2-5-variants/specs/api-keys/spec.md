## MODIFIED Requirements

### Requirement: API-key model picker includes supported image models

The dashboard `GET /api/models` endpoint MUST include `gpt-image-2.5-sunburst`, `gpt-image-2.5-flare`, `gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-1-mini`, as defined by the Images adapter's supported-model allowlist, even when the subscription catalog omits them or is empty. Each ID MUST occur once across subscription, adapter, and enabled source entries. Public subscription entries MUST retain their metadata on collisions; adapter-provided image entries MUST have `imageOnly=true`, `sourceOnly=false`, `supportedReasoningEfforts=[]`, and `defaultReasoningEffort=null`. The API-key create and edit dialogs MUST allow selecting these IDs, saving them in `allowedModels`, and restoring the saved selection when reopened. The Automations model picker MUST exclude image-only adapter entries while continuing to offer eligible subscription models.

#### Scenario: Images remain selectable across registry states

- **GIVEN** a bootstrap, refreshed, or empty subscription catalog that omits image models
- **WHEN** the dashboard requests `GET /api/models`
- **THEN** all six supported Images model IDs appear alongside eligible subscription and source entries
- **AND** adapter-provided image entries advertise no reasoning efforts

#### Scenario: Duplicate image IDs appear once

- **GIVEN** a supported image ID also occurs in the subscription catalog or an enabled model source
- **WHEN** the dashboard requests `GET /api/models`
- **THEN** the ID appears exactly once
- **AND** an existing public subscription entry retains its metadata

#### Scenario: Create and update an image-restricted key

- **WHEN** an operator creates an API key selecting `gpt-image-2` in the allowed-models picker
- **THEN** the saved key has `allowedModels: ["gpt-image-2"]`
- **AND** reopening the edit dialog restores that selection
- **WHEN** the operator replaces the selection with `gpt-image-1-mini` and saves
- **THEN** reopening the edit dialog shows the updated selection

#### Scenario: Create and update a GPT Image 2.5 restricted key

- **WHEN** an operator creates a key selecting `gpt-image-2.5-sunburst`
- **THEN** saving and reopening preserves that exact allowed-model selection
- **WHEN** the operator replaces the selection with `gpt-image-2.5-flare`
- **THEN** saving and reopening preserves Flare without substituting Sunburst or `gpt-image-2`

#### Scenario: Automation picker excludes image-only models

- **GIVEN** the dashboard model response includes subscription, source-only and image-only entries
- **WHEN** an operator opens the Automations model picker
- **THEN** eligible subscription models are selectable
- **AND** image-only and source-only entries are not offered

## ADDED Requirements

### Requirement: GPT Image 2.5 API-key policy and estimated cost remain model scoped

The service MUST apply the exact effective GPT Image 2.5 public ID, resolved after existing API-key model enforcement, when authorizing an Images request and selecting model-scoped limits. A key restricted to one variant MUST NOT dispatch the other variant or `gpt-image-2` through shared parameter or pricing rules. An explicitly enforced permitted model MUST retain its existing precedence over the model supplied by the client.

Each new canonical ID MUST resolve to a nonzero image cost estimate for positive billable token usage. Within the existing aggregate-token estimation contract, each MUST use USD-per-million rates of 5 for uncached input, 2 for cached input, and 30 for output. Cached input MUST be deducted from total input before applying uncached input rates. Successful settlement MUST use image-tool usage rather than host Responses usage. Adapter discovery MUST NOT itself add image-only entries to the public Responses model catalog.

#### Scenario: An allowlist distinguishes the variants

- **GIVEN** an API key allows only `gpt-image-2.5-sunburst` and has no enforced model
- **WHEN** an otherwise valid generation or edit request selects `gpt-image-2.5-flare`
- **THEN** the service returns HTTP 403 with `model_not_allowed` before upstream dispatch
- **AND** a Sunburst request passes this model-policy check, subject to existing quota and authentication rules

#### Scenario: Quota enforcement uses the enforced variant

- **GIVEN** an API key enforces and permits `gpt-image-2.5-flare`, with an exhausted Flare-scoped limit
- **WHEN** a generation or edit request supplies `gpt-image-2.5-sunburst` with otherwise valid parameters
- **THEN** the request is rejected by the existing quota error path before upstream dispatch
- **AND** supplying another model does not bypass the Flare-scoped limit

#### Scenario: Positive image usage contributes to estimated cost

- **WHEN** a successful request for either variant reports 1000 image-tool input tokens, including 200 cached tokens, and 100 image-tool output tokens
- **THEN** its estimated image cost is USD 0.0074 under the aggregate-token contract
- **AND** a host-model usage record does not create a second image settlement

#### Scenario: Dashboard admission does not broaden public Responses discovery

- **GIVEN** neither new image ID exists in the subscription catalog or a configured public model source
- **WHEN** a client lists public `/v1/models`
- **THEN** the new adapter-only IDs are not injected solely because they are selectable in dashboard API-key policy
