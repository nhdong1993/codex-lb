## ADDED Requirements

### Requirement: GPT Image 2.5 variants are accepted by the Images adapter

The Images adapter MUST accept the exact IDs `gpt-image-2.5-sunburst` and `gpt-image-2.5-flare` on `/v1/images/generations`, `/v1/images/edits`, and their `/backend-api/codex/images/*` equivalents. This MUST apply to the existing generation JSON, edit multipart, and Codex edit data-URL inputs, for both streaming and non-streaming output. Existing trailing-slash and mounted-path behavior MUST remain equivalent for these IDs.

After existing request-schema admission, the effective public image model MUST be the API key's `enforced_model` when present, otherwise the explicit requested model or configured image default. Cross-field parameter validation, allowed-model checks, model-scoped reservations, tool forwarding, and request accounting MUST use that effective public model. The adapter MUST forward that effective ID unchanged in the internal `image_generation` tool's `model`, independently of the Responses host model. An enforced non-image model MUST continue to produce HTTP 400 with `param: model` on the Images routes.

The accepted model set MUST remain closed: this addition MUST NOT admit arbitrary `gpt-image-*` strings or dated GPT Image 2.5 snapshots. The configured default behavior MUST remain unchanged, with `gpt-image-2` as the built-in default; either new ID MUST also be usable as the existing `images_default_model` setting.

#### Scenario: Either variant reaches generation and edit tools unchanged

- **GIVEN** an authorized, valid image generation or edit request using either new ID and no API-key enforced model
- **WHEN** any supported Images route processes the request
- **THEN** the internal image tool receives the exact requested ID
- **AND** the internal host selection follows the existing Responses host policy
- **AND** a successful upstream image result is translated into the existing route-specific JSON or SSE response shape

#### Scenario: A configured variant resolves an omitted model

- **GIVEN** `images_default_model` is set to either new ID and the API key has no enforced model
- **WHEN** a valid generation or edit request omits `model`
- **THEN** validation, forwarding, authorization, and accounting use that configured ID
- **AND** without a configuration override an omitted model still resolves to `gpt-image-2`

#### Scenario: Enforced model determines the parameter profile

- **GIVEN** an API key enforces `gpt-image-2` and permits that model
- **WHEN** the client requests either GPT Image 2.5 variant with `quality=max`
- **THEN** the request fails with HTTP 400 and `param: quality` under the effective `gpt-image-2` profile
- **AND** no upstream request is opened

#### Scenario: An enforced variant takes precedence over request and default

- **GIVEN** an API key enforces and permits `gpt-image-2.5-flare`
- **WHEN** a generation or edit request supplies `gpt-image-2.5-sunburst`, or omits `model`, with parameters valid for Flare
- **THEN** validation, the image tool, allowed-model checks, reservations, and request accounting use `gpt-image-2.5-flare`
- **AND** the Responses host remains independent of that enforced image ID

#### Scenario: Unknown or unplanned snapshot IDs are rejected

- **WHEN** an Images request uses `gpt-image-2.5-unknown` or an unsupported dated snapshot
- **THEN** the service returns HTTP 400 with an OpenAI `invalid_request_error` and `param: model`
- **AND** it does not open an upstream request

### Requirement: GPT Image 2.5 parameters have a distinct validation profile

For the two supported GPT Image 2.5 IDs, the adapter MUST accept quality `auto`, `low`, `medium`, `high`, `xhigh`, and `max`, with `auto` as the default. It MUST accept `size=auto` or positive `WIDTHxHEIGHT` dimensions whose edges are multiples of 16, each edge is at most 3840 pixels, longer-to-shorter edge ratio is at most 3:1, and total pixels are between 655360 and 8294400 inclusive.

Background MUST accept `auto`, `opaque`, and `transparent`. Explicit `transparent` MUST require `output_format=png` or `webp`; explicit `transparent` with `jpeg` MUST return HTTP 400 with `param: output_format`. These models MUST reject supplied non-null `input_fidelity` with `param: input_fidelity` under this adapter contract. The existing `n=1`, `partial_images` range of 0 through 3, and remaining common parameter limits MUST remain in force.

Invalid parameters MUST return the existing OpenAI `invalid_request_error` envelope before upstream dispatch. Accepted values MUST be preserved in the internal tool configuration, subject to the existing streaming-only handling of `partial_images`. The added quality/background permissions MUST NOT change legacy model validation.

#### Scenario: Extended quality and custom size are preserved

- **WHEN** a valid generation or edit request selects either variant with `quality=xhigh` or `max` and `size=1536x864`
- **THEN** the service accepts and forwards those values unchanged
- **AND** streaming output preserves upstream-supplied quality/size metadata in the existing route-specific SSE events
- **AND** non-streaming output retains the existing `{created, data, usage?}` envelope without adding quality/size fields

#### Scenario: Transparent output requires a compatible format

- **WHEN** either variant requests `background=transparent` with `output_format=png` or `webp`
- **THEN** the request passes background/format validation
- **WHEN** the same request specifies `output_format=jpeg`
- **THEN** it fails before dispatch with HTTP 400, `type: invalid_request_error`, and `param: output_format`

#### Scenario: Invalid dimensions and extended legacy quality are rejected

- **WHEN** either variant requests a size outside any specified dimension, ratio, or pixel-count boundary
- **THEN** it fails before dispatch with HTTP 400 and `param: size`
- **WHEN** a legacy supported image model requests `quality=xhigh` or `max`
- **THEN** it still fails with HTTP 400 and `param: quality`

#### Scenario: Unsupported fidelity and multi-image requests remain rejected

- **WHEN** either variant supplies `input_fidelity=low` or `high`, with otherwise valid parameters
- **THEN** the service returns HTTP 400 with `param: input_fidelity`
- **WHEN** an otherwise valid request specifies `n=2`
- **THEN** the service returns HTTP 400 with `param: n`

### Requirement: GPT Image 2.5 requests preserve public identity and upstream failures

For either variant, policy checks, model-scoped reservations, request logs, and successful route telemetry MUST use the effective public image ID after existing API-key enforcement. A successful image result MUST use the existing image-tool usage settlement contract and MUST NOT settle a second time as the host model. Unsupported upstream model or parameter failures MUST retain the existing OpenAI-compatible error translation; after effective-model resolution, the adapter MUST NOT silently replace a variant or quality with a different value to turn that failure into success.

#### Scenario: Public identity is retained through settlement

- **WHEN** either variant returns a successful image result with image-tool token usage
- **THEN** request logging and image-route telemetry retain the effective public ID
- **AND** a limited API-key reservation is settled exactly once using captured image-tool usage

#### Scenario: Upstream model or quality rejection is surfaced

- **WHEN** upstream rejects an accepted variant or its requested quality
- **THEN** the client receives the existing structured failure representation for its JSON or streaming route
- **AND** the adapter does not retry using a substituted image model or lower quality
- **AND** the reservation is finalized or released by the existing single-owner failure path

## MODIFIED Requirements

### Requirement: Image routes participate in usage accounting and policy

The system SHALL apply API-key allowed-model policy and model-scoped usage
limits to `/v1/images/*` using the effective public image model: the API key's
`enforced_model` when present, otherwise the requested model or configured image
default. The system SHALL record that effective public image value in the
request log's `model` column once the
upstream response id becomes known. A successful image generation or edit that
owns a limited API-key reservation SHALL transfer that reservation exactly once
to persistence-drained settlement using captured `tool_usage.image_gen` tokens,
while the internal Responses stream SHALL NOT receive a second settlement
owner. Failed or cancelled finalization SHALL preserve the completed public
image response and transfer ownership to the tracked retrying release fallback.

#### Scenario: API key allowed-model policy blocks gpt-image-2

- **GIVEN** an API key has no enforced model
- **WHEN** its `allowed_models` list does not include `gpt-image-2`
- **THEN** requests to `/v1/images/generations` or `/v1/images/edits` with `model=gpt-image-2` return 403 `model_not_allowed`

#### Scenario: Request log surfaces the publicly requested image model

- **WHEN** an `/v1/images/*` request completes successfully against an internal host Responses model (for example `gpt-5.5`)
- **THEN** the resulting `request_logs` row has `model` equal to the effective public image value after API-key enforcement (for example `gpt-image-2`) so dashboards and usage views surface the user-visible model rather than the internal host model

#### Scenario: Failed image-token settlement retains tracked release ownership

- **GIVEN** a limited API key owns a reservation for a successful image generation or edit request
- **AND** the internal Responses stream receives no API-key reservation
- **AND** the image adapter captures authoritative `tool_usage.image_gen` tokens
- **WHEN** tracked finalization fails or is cancelled while the reservation remains `reserved`
- **THEN** the completed public Images JSON response or SSE completion remains available
- **AND** settlement ownership transfers to a persistence-drained fallback release task
- **AND** transient release failures keep that task tracked and retrying until release succeeds or graceful persistence drain reports timeout
- **AND** a successful fallback restores pre-reserved quota exactly once without recording `response.usage` or starting a second image settlement

### Requirement: OpenAI-compatible image generation endpoint

The system SHALL expose `POST /v1/images/generations` and accept the OpenAI Images API request shape (`model`, `prompt`, `n`, `size`, `quality`, `background`, `output_format`, `output_compression`, `moderation`, `partial_images`, `stream`, `user`). The endpoint MUST require `model` to start with `gpt-image-` and MUST treat `gpt-image-2` as the default if unspecified. The endpoint MUST NOT expose the internal "host" Responses model used to invoke the built-in `image_generation` tool.

#### Scenario: Compatible image generation request returns a JSON envelope

- **WHEN** a client sends `POST /v1/images/generations` with `model=gpt-image-2`, a non-empty `prompt`, and no `stream`
- **THEN** the service returns 200 with a JSON body of shape `{created, data: [{b64_json, revised_prompt}], usage}` containing exactly one entry

#### Scenario: Unsupported model is rejected

- **WHEN** a client sends `POST /v1/images/generations` with `model` not starting with `gpt-image-`
- **THEN** the service returns 400 with OpenAI `invalid_request_error` and `param: model`

#### Scenario: Per-model parameter rules are enforced for gpt-image-2

- **WHEN** a client sends `gpt-image-2` with `background=transparent` or `input_fidelity=low|high`, or with `size` violating the gpt-image-2 size constraints (max edge ≤ 3840 px, both edges multiples of 16, ratio ≤ 3:1, total pixels in [655_360, 8_294_400])
- **THEN** the service returns 400 with OpenAI `invalid_request_error` describing the rejected parameter

#### Scenario: Per-model parameter rules are enforced for legacy gpt-image models

- **WHEN** a client sends `gpt-image-1.5`, `gpt-image-1`, or `gpt-image-1-mini` with `size` outside `{1024x1024, 1536x1024, 1024x1536, auto}`
- **THEN** the service returns 400 with OpenAI `invalid_request_error` and `param: size`

#### Scenario: Multi-image requests are rejected until upstream support arrives

- **WHEN** a client sends `/v1/images/generations` or `/v1/images/edits` with `n > 1`
- **THEN** the service returns 400 with OpenAI `invalid_request_error` and `param: n`, with a message that explains the upstream `image_generation` tool does not yet support multi-image responses
- **AND** no settings override SHALL raise the accepted request `n` above 1 until codex-lb implements client-side fan-out or upstream exposes first-class multi-image support

#### Scenario: Missing model defaults to images_default_model

- **GIVEN** the API key has no enforced model
- **WHEN** a client sends `/v1/images/generations` or `/v1/images/edits` without `model`
- **THEN** the service uses `images_default_model` (default `gpt-image-2`) as the publicly-effective model for validation, request log accounting, and the internal `image_generation` tool config
