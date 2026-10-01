## Why

Requests for `gpt-image-2.5-sunburst` and `gpt-image-2.5-flare` currently fail local Images API validation before reaching the upstream image tool. Official OpenAI documentation describes both IDs and additional output options, while upstream codex-lb issue [#2304](https://github.com/Soju06/codex-lb/issues/2304) remains open.

## What Changes

- Accept both exact model IDs for generation and editing on the existing OpenAI-compatible and Codex-base routes, including JSON and streaming responses.
- Add a GPT Image 2.5 parameter profile with `xhigh`/`max` quality, constrained custom sizes, and transparent PNG/WebP output.
- Preserve the effective public model, after existing default resolution and API-key model enforcement, in the Responses image tool, policy checks, usage accounting, request logs, and bounded telemetry. Validate parameters against that effective model.
- Expose the two IDs in the existing API-key model picker through the shared adapter allowlist.
- Add regression coverage at the public HTTP routes, the dashboard policy surface, and cost/settlement paths; document the distinction between adapter support and upstream subscription availability.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `images-api-compat`: Exact GPT Image 2.5 model admission, parameter validation, payload preservation, and error behavior.
- `api-keys`: Image-model discovery and policy/usage coverage for the two new IDs.

## Impact

- Primary implementation: `app/core/openai/images.py`; inspect `app/modules/proxy/images_service.py`, `app/modules/proxy/api.py`, `app/modules/proxy/images_observability.py`, and `app/modules/dashboard/api.py` for propagation.
- Pricing: verify the existing `gpt-image-2*` fallback and add explicit canonical entries for the new IDs without redesigning mixed-modality costing.
- Tests: image schema/translation/route suites, model catalog and API-key picker suites, pricing/settlement tests, and SDK compatibility coverage.
- No new dependency, database migration, environment setting, or dashboard navigation item is required. This is an additive, zero-configuration adapter capability.

## Non-goals

Changing the default `gpt-image-2`, API-key model enforcement, or the internal Responses host selection; supporting arbitrary or dated image IDs; multi-image fan-out; extending `input_fidelity` to GPT Image 2.5 without a verified tool contract; changing legacy model semantics, non-streaming response fields, or mask translation; proving subscription entitlement from HTTP status alone; production deployment.

Implementation was approved after plan review. Progress and verification are recorded in `tasks.md` and `verify-report.md`.
