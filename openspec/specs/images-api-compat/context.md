# Images API compatibility context

## Purpose and scope

codex-lb exposes OpenAI-compatible `/v1/images/*` endpoints and Codex-native
aliases below `/backend-api/codex/images/*`. The native aliases let Codex's
built-in `$imagegen` tool use the same account selection, validation, usage
accounting, and response pipeline as other image clients.

Codex client setup is part of this compatibility boundary. A working server
route is insufficient when a custom-provider gateway hides the image tool
before it makes an HTTP request.

## Codex provider eligibility

Codex has two distinct provider-authentication paths that can make built-in
image generation eligible:

1. A provider with `requires_openai_auth = true` and current authentication
   backed by Codex. This is the path used by the standard codex-lb examples in
   the README; it does not require an actor-authorization header.
2. A provider that deliberately skips OpenAI login with
   `requires_openai_auth = false` and supplies a non-empty
   `x-openai-actor-authorization` entry in `http_headers`.

For the second path, a minimal provider fragment is:

```toml
base_url = "http://127.0.0.1:2455/backend-api/codex"
wire_api = "responses"
requires_openai_auth = false
http_headers = { "x-openai-actor-authorization" = "codex-lb" }
```

The static `codex-lb` value is a non-secret client capability marker. It does
not authenticate requests to codex-lb. A deployment that requires codex-lb API
key authentication must still configure `env_key = "CODEX_LB_API_KEY"` and
provide that credential independently.

## Verified upstream behavior

This contract was checked against `openai/codex` commit
[`0d1733b5e9ea027a0ff9d75cc3e11103f045f1ce`](https://github.com/openai/codex/commit/0d1733b5e9ea027a0ff9d75cc3e11103f045f1ce)
(2026-07-10):

- Codex recognizes the actor-authorized path only when
  `requires_openai_auth` is false and `http_headers` contains a
  case-insensitive, non-empty `x-openai-actor-authorization` entry
  ([source](https://github.com/openai/codex/blob/0d1733b5e9ea027a0ff9d75cc3e11103f045f1ce/codex-rs/model-provider-info/src/lib.rs#L400-L408)).
- Image-tool planning accepts either that actor-authorized path or
  `requires_openai_auth = true` with current Codex-backend authentication. It
  also checks provider image-generation capability and model image input
  modality before exposing the tool
  ([source](https://github.com/openai/codex/blob/0d1733b5e9ea027a0ff9d75cc3e11103f045f1ce/codex-rs/core/src/tools/spec_plan.rs#L372-L399)).
- The standalone image extension applies the corresponding provider eligibility
  checks before registering its tool
  ([source](https://github.com/openai/codex/blob/0d1733b5e9ea027a0ff9d75cc3e11103f045f1ce/codex-rs/ext/image-generation/src/extension.rs#L36-L45)).
- The published Codex configuration schema supports provider `http_headers` as
  a string-to-string map in `config.toml`
  ([configuration reference](https://developers.openai.com/codex/config-reference/)).

These conditions are alternatives. Adding the actor marker to a provider that
keeps `requires_openai_auth = true` does not activate the actor-authorized path.

## Constraints and security boundary

- The marker MUST NOT be described as authentication accepted by codex-lb.
- The marker does not replace `Authorization: Bearer ...` when API-key auth is
  enabled.
- The header value must be non-empty. No secret storage or rotation mechanism is
  appropriate for the static `codex-lb` value.
- The provider `base_url` remains the Codex base, not `/v1`, because the built-in
  image client joins `images/generations` and `images/edits` directly onto it.

## Failure modes and operations

- A `requires_openai_auth = false` provider without the marker does not satisfy
  the actor-authorized eligibility path.
- Provider capability state is initialized for a thread. Start a new Codex
  session after changing provider eligibility settings.
- A missing or invalid codex-lb API key still produces the normal proxy
  authentication error even when the actor marker is present.
- Route-level validation and upstream errors remain governed by the normative
  requirements in [spec.md](./spec.md).

## Example user flow

1. Choose the Codex-backed authentication path documented in the README, or
   configure both `requires_openai_auth = false` and the actor marker.
2. Preserve `env_key = "CODEX_LB_API_KEY"` when the deployment requires it.
3. Start a new CLI or IDE session and invoke `$imagegen`.
4. When the remaining model and feature gates allow the tool, Codex posts to
   `/backend-api/codex/images/generations` or
   `/backend-api/codex/images/edits`; codex-lb handles the request through the
   existing Images compatibility pipeline.

## GPT Image 2.5 variants

The adapter accepts the exact names `gpt-image-2.5-sunburst` and
`gpt-image-2.5-flare`. Their parameter and policy contracts are in
[spec.md](./spec.md#requirement-gpt-image-25-variants-are-accepted-by-the-images-adapter).
The separate 2.5 profile adds `xhigh`/`max` quality and transparent PNG/WebP
output while reusing Image 2 geometry validation. It avoids changing legacy
model behavior or admitting arbitrary future names. The built-in default stays
`gpt-image-2`; the existing `CODEX_LB_IMAGES_DEFAULT_MODEL` setting can select
either variant without a new setting or migration.

API-key `enforced_model` takes precedence over a valid requested model or the
configured default. Validation, authorization, quota, the image tool, and
accounting use that effective public ID. The Responses host remains independent.
For example, a key pinned to Image 2 rejects a Sunburst request with `quality=max`
because the effective Image 2 profile does not accept that quality. A key that
only allows Sunburst, without an enforced model, rejects Flare.

A generation request using an allowed Sunburst key can send:

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

The same options work with Flare and with the existing edit upload/data-URL
inputs. Explicit transparency with JPEG fails locally. Explicit non-null
`input_fidelity` remains unsupported for these variants in this adapter; the
general OpenAI edit reference does not establish its Codex subscription-tool
behavior. Editing retains existing image/mask attachment translation: the mask
is an additional image plus a prompt hint, without a new native inpainting
contract.

Non-streaming responses keep `created`, `data`, and optional `usage`. Existing
SSE events preserve supplied quality, size, background, and format; missing
metadata is not synthesized. The locked Python SDK accepts both model strings
and decodes JSON/SSE at runtime, but its quality annotations predate `xhigh` and
`max`. Callers can send extended qualities through `extra_body={"quality":
"max"}`. This does not promise strict enum compatibility in older clients.

The canonical 2.5 pricing entries retain the project's aggregate-token estimate
of USD 5/2/30 per million input/cached-input/output tokens. Official
[pricing](https://developers.openai.com/api/docs/pricing), checked 2026-09-25,
separates image input/cached input/output (8/2/30) and text input/cached input
(5/1.25). The existing accounting model cannot express this split. For 1000
image-tool input tokens including 200 cached, plus 100 output tokens, the
estimate is `(800*5 + 200*2 + 100*30)/1e6 = $0.0074`. Host Responses counters
are not charged as image usage; missing image-tool usage remains uncharged.

Local tests use controlled upstream events and disposable databases. They prove
adapter admission, forwarding, policy, response translation, and accounting.
They do not prove account entitlement or which variant upstream actually runs.
No live upstream generation was performed for this change. Upstream model or
quality errors are surfaced without silently replacing the effective request.
OpenAI's [image guide](https://developers.openai.com/api/docs/guides/image-generation)
and [tool guide](https://developers.openai.com/api/docs/guides/tools-image-generation)
provide the public feature references; subscription availability remains an
upstream property.
