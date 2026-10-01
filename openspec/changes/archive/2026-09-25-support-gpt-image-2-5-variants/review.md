# Plan review — 2026-09-25

Scope: review of the planning artifacts against the current local implementation and official OpenAI documentation. This is not implementation verification or a production readiness report.

## Findings addressed

### P1 — Requested-model preservation conflicted with API-key enforcement

The original delta required the literal requested ID to survive unchanged and its policy scenario rejected Flare for a Sunburst-only key without excluding an enforced model. Both image handlers already resolve `enforced_model` before cross-field validation (`app/modules/proxy/api.py`, `_proxy_images_generation_request`, `_proxy_images_edit_request`). Implementing the original wording could bypass or break that existing operator policy.

Resolution: define effective public model precedence explicitly, preserve the effective ID in tool/policy/accounting, and qualify the no-substitution guarantee as applying after model enforcement. Add generation/edit cases for a 2.5 request enforced to Image 2, a request/default enforced to a 2.5 variant, non-image enforcement, and an exhausted limit on the enforced variant. Keys without an enforced model retain exact per-variant admission.

### P2 — Non-streaming metadata preservation was an unintended API expansion

The original plan promised quality/size preservation for JSON and SSE. `V1ImageResponse` currently contains only `created`, `data`, and optional `usage`, and `images_response_from_responses` does not extract the extra metadata. Only SSE builders preserve those fields. A direct local translation probe confirmed quality/size are absent from JSON even when present upstream.

Resolution: retain the existing JSON envelope and limit metadata assertions to existing SSE fields. Do not widen the JSON schema or synthesize omitted upstream metadata under this model-admission change.

### P2 — SDK compatibility omitted the locked SDK's older quality types

The installed OpenAI Python SDK accepts string model IDs but its request quality annotations and streamed completion enums omit `xhigh`/`max`. Directly adding typed calls with those values would not establish the promised compatibility, and a blanket claim could imply strict validation support in older clients.

Resolution: specify the SDK's `extra_body` path for extended values, keep direct HTTP tests authoritative, and distinguish normal runtime parsing from strict enum validation. Two local `httpx.MockTransport` probes confirmed both model IDs transmit `quality=max` through `extra_body` and the normal generation SSE parser retains `max`. Those probes do not cover edit multipart or every quality; the implementation checklist still requires that coverage.

## Coverage clarified

- Concrete inclusive pixel/edge/ratio boundaries and invalid adjacent sizes are now listed in `design.md`.
- Limited-key tests must supply different image-tool and host token counters, so billing the wrong source fails visibly. Missing image usage retains the existing behavior without fabricating counters.
- Test commands must use an explicit disposable database, including both database environment variables used by the project.
- Existing mask forwarding is identified as image attachment plus a prompt hint; this change does not claim native inpainting-mask correctness.

## Retained limitations

- Official output options are supported at the adapter/forwarding boundary. Public API documentation and mocked success do not prove Codex subscription entitlement or the upstream variant actually executed. See the [official tool guide](https://developers.openai.com/api/docs/guides/tools-image-generation) and [upstream discussion](https://github.com/Soju06/codex-lb/issues/2304).
- Explicit `input_fidelity` remains out of scope for these two IDs; its absence from this adapter contract is not a claim that OpenAI universally rejects it.
- The 5/2/30 cost estimate preserves the project's aggregate-token approximation; it is not modality-accurate OpenAI billing. Explicit canonical entries isolate the two variants from later changes to the broad `gpt-image-2*` fallback.
- Dated snapshots remain outside the requested two-ID scope.

## Validation

- Revised change: `openspec validate support-gpt-image-2-5-variants --strict` passed using the installed cached CLI.
- Relative Markdown links and trailing whitespace checks passed for the revised artifacts.
- Local probes confirmed current price fallback for both IDs, the JSON response-field boundary, and normal SDK generation streaming with `quality=max` (two mock-transport cases, no upstream calls).
- All 19 implementation tasks remain unchecked. No application code, dependencies, main specs, or deployment state changed during this review. Full regression suites belong to the implementation phase.

No unresolved plan blocker was found within the stated adapter scope. Upstream behavior remains an explicitly unverified external dependency.
