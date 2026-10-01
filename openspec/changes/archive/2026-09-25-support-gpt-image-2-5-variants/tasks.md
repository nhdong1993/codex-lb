## 1. Establish regression coverage

- [x] 1.1 Add parameterized failing tests for both new IDs in generation and edit schemas, plus public generation/multipart-edit route tests with a controlled upstream; verify baseline failures are local unsupported-model errors.
- [x] 1.2 Extend the model parameter matrix for all six qualities, the exact geometry boundaries in `design.md`, transparent PNG/WebP (including default format), transparent JPEG rejection, unsupported fidelity, unknown/snapshot IDs, and existing `n`/partial-image limits; verify failures identify the intended parameter and old-model expectations stay intact.

## 2. Implement admission and parameter handling

- [x] 2.1 Add the exact two-member model group to the shared allowlist and a separate 2.5 parameter profile in `app/core/openai/images.py`, reusing constrained geometry validation; verify the schema matrix passes and old models still reject extended quality.
- [x] 2.2 Verify generation/edit translation preserves the effective public ID after default resolution and API-key enforcement, extended quality, dimensions, transparency, edit action, and existing image/mask inputs; verify enforced model precedence and independent top-level host selection, changing translation only where a focused test exposes a gap.
- [x] 2.3 Verify both variants return image bytes and image-tool usage in the existing JSON envelope, while route-specific SSE preserves upstream quality/size/background/format metadata including `xhigh`/`max`; verify absent metadata is not fabricated and leave non-streaming response fields unchanged.

## 3. Verify route compatibility and failure handling

- [x] 3.1 Extend HTTP integration coverage to generation JSON, canonical multipart edits, Codex generation aliases, and Codex JSON data-URL edits for both IDs; verify outbound model equality and existing JSON/SSE envelopes, including representative trailing-slash and mounted-path cases.
- [x] 3.2 Exercise upstream model/parameter rejection before the first SSE chunk and failure after streaming begins; verify existing external errors, no model/quality substitution, and exactly-once reservation release or settlement.
- [x] 3.3 Extend the locked OpenAI SDK compatibility test with both new IDs for generation and editing; use `extra_body` for `xhigh`/`max` where its current type annotations lack those values, and verify outbound values plus normal runtime JSON/SSE decoding. Document strict-client enum limitations instead of requiring an unrelated SDK upgrade.

## 4. Preserve policy, costs, and observability

- [x] 4.1 Add exact canonical pricing entries in `app/core/usage/pricing.py` using the documented existing aggregate estimate; verify canonical lookup wins over `gpt-image-2*` and the 1000 input / 200 cached / 100 output example costs USD 0.0074 for each variant.
- [x] 4.2 Test per-variant policy without an enforced model, configured defaults, and `enforced_model` precedence on both public image routes; verify Image 2 enforcement rejects 2.5-only quality, 2.5 enforcement uses the 2.5 profile, non-image enforcement returns `param: model`, and an exhausted effective-model limit cannot be bypassed by supplying another ID.
- [x] 4.3 Extend limited-key success tests for both public IDs using distinct image-tool and host usage counters to verify nonzero estimated cost, public request-log identity, and exactly-once image settlement; verify missing image usage does not charge host counters, and retain cancellation/finalization regression coverage.
- [x] 4.4 Verify successful image-route logs/metrics identify either new model and invalid names retain bounded labels; inspect captured telemetry for absence of prompt, image bytes, or credential data.

## 5. Expose models in the existing dashboard picker

- [x] 5.1 Extend `tests/integration/test_v1_models.py` for all six supported image IDs, empty/refreshed catalogs, collision deduplication, and image-only metadata; verify adapter admission alone does not inject the new IDs into public `/v1/models`.
- [x] 5.2 Extend API-key create/edit picker tests and fixtures so Sunburst and Flare selections survive save/reopen and replacement; verify Automations excludes adapter-only image entries without adding a frontend allowlist.
- [x] 5.3 Capture before/after picker screenshots using synthetic data and store them under this change; verify the new IDs are searchable and selected values remain readable.

## 6. Validate and finalize the implementation

- [x] 6.1 Run the focused backend suites below against the test harness's disposable database, together with affected API-key and alias/mount tests; record commands and passing counts in `verify-report.md` and confirm the external regression cases pass.
- [x] 6.2 Run affected frontend picker/create/edit/Automations tests, frontend type checking, `make lint`, and `uv run ty check`; record any unrelated pre-existing failures separately and verify the change introduces none.
- [x] 6.3 Prepare stable context covering adapter guarantees, enforcement precedence, JSON/SSE and SDK limits, estimated-cost limitations, example requests, and automated versus live evidence for sync during task 6.4. If an authorized live smoke is available, record its bounded result; otherwise explicitly record that upstream variant identity remains unverified.
- [x] 6.4 Verify implementation against every delta requirement, sync delta specs and stable context, run strict change/main-spec validation, and archive only after implementation verification; confirm all tasks are complete and no unrelated workspace changes are included.

## Verification commands

Backend starting set (add affected policy/alias tests discovered during implementation):

```sh
uv run pytest tests/unit/test_images_schemas.py tests/unit/test_images_translation.py tests/unit/test_pricing.py tests/integration/test_proxy_images.py tests/integration/test_v1_models.py tests/e2e/test_openai_sdk_compat.py -q
make lint
uv run ty check
```

OpenSpec:

```sh
openspec validate support-gpt-image-2-5-variants --strict
openspec validate --specs --strict
```

The CLI was absent from `PATH` during planning. Its existing cached installation works as `node /home/dong01/.npm/_npx/1cc60f4d9dd04053/node_modules/@fission-ai/openspec/bin/openspec.js`; use it if `openspec` remains unavailable. This cache path is environment-specific, not a repository dependency. Use the project test harness and explicitly point `CODEX_LB_TEST_DATABASE_URL` and `CODEX_LB_DATABASE_URL` at the same newly allocated disposable SQLite database before pytest; do not inherit an operator database URL.

This checklist authorizes no deployment, commit, push, or PR publication. The operator approved implementation after the plan review. Checked tasks have implementation and verification evidence; final results are recorded in `verify-report.md`.
