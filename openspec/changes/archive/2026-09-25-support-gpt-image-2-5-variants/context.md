# GPT Image 2.5 adapter support context

## Purpose and scope

Planning date: 2026-09-25. This change removes local rejection of the two named image variants and specifies their supported adapter options. Requirements live in the [Images delta](./specs/images-api-compat/spec.md) and [API-key delta](./specs/api-keys/spec.md). Implementation was approved after the plan review; see `verify-report.md` for local evidence.

## Evidence

- Upstream codex-lb `main` at [`09a140fa`](https://github.com/Soju06/codex-lb/blob/09a140fa9979a908e60acc97232367e0a08ef32c/app/core/openai/images.py#L49-L54) still lacks both IDs. [Issue #2304](https://github.com/Soju06/codex-lb/issues/2304) is open. Comments distinguish local forwarding tests from proof of actual upstream model identity.
- Before this change, local `V1ImagesGenerationsRequest` and `V1ImagesEditsForm` validation rejected both IDs. Local `ResponsesRequest` accepts them inside an `image_generation` tool descriptor; no live upstream image generation was performed during investigation.
- OpenAI documents [Sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst) and [Flare](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare). Its [image generation guide](https://developers.openai.com/api/docs/guides/image-generation) documents extended quality, custom dimensions, and transparency. The [tool guide](https://developers.openai.com/api/docs/guides/tools-image-generation) places image-model selection in the tool while using a mainline host model.
- The [edit reference](https://developers.openai.com/api/reference/resources/images/methods/edit) describes a general `input_fidelity` option without resolving this adapter's model-specific subscription-tool support. This plan keeps that option unavailable for the new IDs.

## Decisions and constraints

Use exact IDs and a distinct 2.5 validation profile. A name-only patch would reject documented output options. A wildcard acceptance rule would admit unintended models. The plan retains the current default and single-image limit, uses existing dashboard model discovery, and adds no runtime setting or schema migration.

The public ID means the effective image model after existing API-key enforcement: `enforced_model` takes precedence over a valid requested model or configured default. Parameters, limits, the tool, and accounting all use that effective ID. For example, a key pinned to `gpt-image-2` still rejects a Sunburst request with `quality=max`. This policy override is distinct from an adapter silently falling back after an upstream failure.

This adapter guarantee is acceptance, validation, and faithful forwarding. Account entitlement, upstream aliases, and the model actually executed remain properties of the upstream service. A successful HTTP response does not by itself identify that model.

## Response and client compatibility limits

Non-streaming responses retain `created`, `data`, and optional `usage`; quality, size, background, and format are only forwarded in existing SSE events when upstream supplies them. This increment adds no JSON metadata fields.

The installed Python SDK accepts model strings but lacks `xhigh`/`max` in its quality annotations. The compatibility tests exercise extended values via `extra_body` and the normal runtime parser; it does not promise strict enum validation in older external SDKs. Direct HTTP tests cover the wire behavior independently.

Editing reuses current image/mask attachment translation, which represents a mask as another image plus a prompt hint. This is not evidence of native inpainting-mask semantics. Extending the model list does not repair or re-certify that existing behavior.

## Cost estimation limitation

The current alias `gpt-image-2*` already gives the new names a nonzero estimate. This change makes their canonical prices explicit while preserving the existing aggregate-token estimate. Official [pricing](https://developers.openai.com/api/docs/pricing) for both variants separates image input/cached input/output (8/2/30 USD per million) from text input/cached input (5/1.25). The project's single input-rate model uses 5/2/30 and cannot represent those distinctions exactly. Improving modality-aware billing is outside this change.

## Failure modes

- Upstream may reject the variant or an extended quality despite local acceptance; the existing error path remains authoritative.
- A request can succeed while upstream model identity remains unobservable; verification reports must state that limit.
- Unknown names and dated snapshots remain outside this increment.
- Transparency with JPEG fails locally; PNG or WebP is required for explicitly transparent output.
- A key allowing Sunburst does not allow Flare. Shared parameter validation does not grant shared authorization.

## Example after implementation

An operator selects `gpt-image-2.5-sunburst` in an API key's allowed models and submits:

```json
{
  "model": "gpt-image-2.5-sunburst",
  "prompt": "Create a simple red circle on a transparent background",
  "quality": "xhigh",
  "size": "1024x1024",
  "background": "transparent",
  "output_format": "png"
}
```

With no enforced model on the key, the generation route validates this profile and puts the requested model and options in the image tool. The host is selected independently. Switching to Flare requires the API key to permit Flare; omitting `model` uses the existing configured default unless the key explicitly enforces another model.

## Verification and rollout notes

Automated tests use controlled upstream events and a disposable database. Capture before/after API-key picker screenshots with synthetic data. Record adapter results separately from any optional live smoke result. After implementation verification, promote stable context to the owning main capability docs and archive this change. Deployment remains a later operator action through the existing HA rollout.
