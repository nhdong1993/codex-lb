## Context

See [proposal.md](./proposal.md) for the problem and [context.md](./context.md) for source evidence. Current request schemas and `resolve_public_image_model` share a closed allowlist in `app/core/openai/images.py`. The dashboard and telemetry already consume that allowlist. `images_service.py` copies the public model into the image tool and uses a separately selected Responses host.

Pricing currently matches both new names through `gpt-image-2*`; it is therefore already nonzero, but this is an implicit family match. `ModelPrice` and persisted accounting use aggregate input counts rather than independent text/image input rates.

## Goals / Non-Goals

**Goals:** Add a small explicit parameter profile, reuse the existing request pipeline, and demonstrate correctness through the externally failing HTTP routes. Keep compatibility decisions centralized.

**Non-Goals:** Reworking routing, task ownership, the pricing data model, or public Responses discovery. Detailed product boundaries are in the proposal.

## Decisions

### 1. Explicit model group with a shared geometry validator

Add a two-member GPT Image 2.5 set and include it in `SUPPORTED_IMAGE_MODELS`. Use membership in the existing Image 2 group or the new group for constrained dimensions, while keeping quality and background checks separate. Adjust new-model validation messages to identify the actual requested model.

Adding both names directly to the Image 2 group would preserve obsolete restrictions on quality and transparency. Prefix-based admission would allow unverified names and unbounded telemetry labels. A general capability registry is unnecessary for two variants.

### 2. Implement the documented output options explicitly

The parameter matrix is defined in the [Images delta](./specs/images-api-compat/spec.md). Share geometry validation, add `xhigh`/`max` only to the new profile, and validate transparent output against its file format before dispatch. Keep explicit `input_fidelity` unsupported for these two IDs: the general Images edit schema advertises that field but does not establish its model-specific Codex tool behavior. Document this as a limitation instead of claiming complete OpenAI parity.

Do not silently coerce quality, size, format, or model. Preserve existing handling of `n`, partial images, moderation, compression, uploads, and legacy model validation. Any unrelated legacy compatibility correction belongs in a separate change.

### 3. Reuse payload and response translation

Preserve the current resolution order: schema admission, client model or configured default, API-key `enforced_model` override, cross-field validation, model-policy/limit enforcement, then tool translation. Test overrides in both directions: a 2.5 request pinned to Image 2 rejects `max`, while an Image 2 request pinned to a 2.5 variant can use the effective variant's `max` quality. An enforced image ID belongs in the tool, never in the top-level host model. The no-substitution rule applies after this intentional policy override.

Exercise `images_generation_to_responses_request` and `images_edit_to_responses_request` through real ASGI route tests with a controlled upstream. Prefer assertions over edits where translation already preserves new values. Retain edit action, image/mask forwarding, forced tool choice, current host selection, and route-specific SSE event names. Existing mask forwarding appends an image and a prompt hint; this change does not establish native inpainting-mask semantics.

The non-streaming response currently contains only `created`, `data`, and optional `usage`; keep that shape. SSE partial/completion builders already forward quality, size, background, and output format as supplied by upstream. Test `xhigh`/`max` there without promising those fields in JSON or fabricating missing upstream metadata. Exercise an upstream rejection before streaming and a failure after streaming begins. Keep settlement/release ownership and model-scoped authorization in their current paths.

The installed Python SDK accepts arbitrary model strings but its quality annotations and streaming event literals currently omit `xhigh`/`max`. Test supported SDK calls for both model IDs and use its existing `extra_body` escape hatch for extended quality where needed; assert the exact outbound value and runtime-decoded SSE value. This proves compatibility for the locked SDK's normal parsing path, not strict enum validation in every external client. Keep direct HTTP coverage authoritative for the wire contract and avoid an unrelated dependency upgrade.

### 4. Dashboard discovery comes from the shared allowlist

`app/modules/dashboard/api.py` already generates image-only entries from `SUPPORTED_IMAGE_MODELS`. Extend integration and UI fixtures to cover six entries, duplicate IDs, selection persistence, and Automations filtering. Avoid a second frontend model list. The public `/v1/models` Responses catalog keeps its existing eligibility rules.

### 5. Make cost lookup explicit without expanding billing scope

Add explicit canonical price entries for Sunburst and Flare using the existing aggregate approximation (5/2/30 per million input/cached-input/output tokens). Verify canonical lookup takes precedence over the broad alias. This matches today's effective estimate and prevents a later change to Image 2 pricing from silently repricing 2.5.

This is an internal estimate, not a claim of exact OpenAI invoicing: official image-input and text-input prices differ, and so do their cached-input rates. Preserving distinct modality counts throughout persistence and billing would be a separate change. Test the arithmetic and public-model settlement rather than adding an unrelated billing refactor.

### 6. Verification separates local guarantees from upstream observations

Required automated evidence covers admission, parameters, exact outbound payload, response envelopes, policy, nonzero costs, logs/metrics, and error cleanup. It uses fake upstream responses and a disposable test database.

An optional bounded live smoke, when actual execution is requested and an eligible test account is available, records model, quality, host model, outcome, and sanitized completion metadata. HTTP 200 alone establishes request success, not which image variant ran. If no variant-specific metadata exists, record identity as unverified. Live failures must not trigger automatic model substitution or an expansion of this plan.

## Risks / Trade-offs

- **Subscription tool behavior can differ from the public API** → Keep explicit requests unchanged, propagate errors, and qualify upstream availability separately in verification notes.
- **A shared validator change can alter old models** → Run the existing model/parameter matrix and isolate extended quality/background permissions.
- **A test proves schema admission but misses routing failures** → Use route-level generation/edit coverage for both IDs, JSON/SSE, Codex aliases, and existing slash/mount forms.
- **Pricing is approximate for mixed-modality input** → Preserve the existing estimate, make canonical lookup explicit, and disclose the limitation in context.
- **Workspace already contains unrelated changes** → Scope implementation and review to this change; do not stage, overwrite, or archive unrelated work.

## Verification matrix

Use parameterized extensions of existing tests. Cover both IDs across generation JSON, canonical multipart edits, and Codex JSON edits, with representative alias/slash/mount cases; keep the full parameter boundary matrix at unit level and representative positive/negative boundaries at HTTP level.

| Boundary | Accepted example | Rejected example |
| --- | --- | --- |
| Minimum pixels | `1024x640` (655360) | `1008x640` (645120) |
| Maximum pixels | `3840x2160` (8294400), plus its transpose | `3840x2176` (8355840) |
| Maximum edge | `3840x1280` | `3856x1712` |
| Aspect ratio | `1536x512`, plus its transpose | `1552x512`, plus its transpose |
| Multiple of 16 | `1024x1024` | `1025x1024` |
| Transparent format | PNG/WebP, including omitted format defaulting to PNG | JPEG |

Also cover invalid dimensions (zero, negative, malformed), all six accepted quality values, an invalid quality, and legacy rejection of extended options. Add effective-model override cases, rather than testing only an unrestricted key. For each variant, verify one public route with real limited-key reservation/settlement, plus existing cancellation/finalization regressions. Fake upstream `tool_usage.image_gen` must deliberately differ from host `response.usage` so charging the wrong source fails the test. Include missing image usage: retain current unknown/absent usage semantics without inventing usage or substituting host tokens.

## Migration Plan

No data migration or configuration change is needed. Implement and validate locally, capture picker screenshots, then sync the verified delta/context and archive. A later production rollout follows the existing HA deployment skill when requested. Reverting the patch restores the previous model admission policy; existing saved keys containing these IDs remain stored but requests will again be rejected. Manual runtime mutation is not part of this change.
