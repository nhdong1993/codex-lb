# Implementation verification — 2026-09-25

## Scope and status

Change: `support-gpt-image-2-5-variants`. Production changes are limited to the
closed model allowlist, separate 2.5 parameter checks/shared geometry, and two
canonical aggregate price entries. Existing routing, translation, dashboard
model discovery, policy enforcement, and settlement already propagate the IDs.
No deployment or live upstream generation was performed.

The seven delta requirements are implemented and synced to the two main
capabilities. All 19 tasks are complete; feature verification is complete with
unrelated workspace/test-harness limitations recorded below.

| Dimension | Result |
| --- | --- |
| Completeness | 19/19 tasks; 7/7 delta requirements implemented and synced |
| Correctness | All new-model regression cases pass; existing API-key teardown timeout remains outside feature scope |
| Coherence | Shared allowlist and existing translation/accounting retained; no new setting, migration, dependency, or UI allowlist |

## Requirement mapping

| Requirement | Implementation and regression evidence |
| --- | --- |
| GPT Image 2.5 variants are accepted by the Images adapter | `SUPPORTED_IMAGE_MODELS`; schema admission; generation/multipart edit round trips; `test_image25_routes_preserve_options` across four routes and JSON/SSE; effective-policy, slash, and root-path cases |
| GPT Image 2.5 parameters have a distinct validation profile | `validate_image_request_parameters` and shared size validator; `TestImage25Parameters` covers all six qualities, geometry boundaries, formats, fidelity, n/partial bounds; legacy extended-quality rejection; HTTP parameter rejection |
| GPT Image 2.5 requests preserve public identity and upstream failures | Route telemetry and exact outbound assertions; scoped settlement uses different image/host counters; before/after-stream failures preserve model/quality and error envelope; handoff/cancellation regressions |
| OpenAI-compatible image generation endpoint | Existing default/model behavior retained; omitted-model scenario now explicitly excludes enforced keys; existing default tests and new effective-policy matrix |
| Image routes participate in usage accounting and policy | Existing handler effective-model resolution and settlement path; spec wording now explicitly accounts for `enforced_model`; missing usage releases rather than charging host counters; finalization/release tests retained |
| API-key model picker includes supported image models | Shared allowlist consumed by dashboard; registry-state/collision tests in `test_v1_models.py`; create/save/reopen/replace UI flow; Automations filtering; synthetic browser screenshots |
| GPT Image 2.5 API-key policy and estimated cost remain model scoped | Canonical pricing and `$0.0074` arithmetic; exact per-variant allowlists; env-configured defaults and enforced-model precedence; exhausted effective-model limit; public `/v1/models` non-injection |

SDK runtime coverage uses the locked dependency with `extra_body` for extended
quality, covering both models, generation/editing, and JSON/SSE. Missing upstream
SSE metadata is not fabricated. Unknown/snapshot model HTTP tests verify the
bounded `invalid` telemetry label, `param: model`, and no upstream dispatch.

## Validation evidence

Every pytest run explicitly set `CODEX_LB_TEST_DATABASE_URL` and
`CODEX_LB_DATABASE_URL` to the same disposable SQLite URL below `/tmp`. Real
upstream transport was replaced with controlled events. Environment-specific
logs are below `/tmp/image25-*.log`; this report preserves the meaningful results.

- Baseline before runtime edits: **8 expected failures, 2 passed**, selecting
  new-ID schema/generation/edit cases. Failures were local unsupported-model
  admission, establishing the original externally failing paths.
- Initial schema/model matrix and round trips: **128 passed**.
- Locked SDK new-model matrix: **8 passed**.
- Final handoff/metadata/scoped-settlement group: **48 passed**. Success uses
  image-tool 1000 input/200 cached/100 output versus host 9000/8000 counters;
  quota increases by exactly 7400 microdollars. Missing image usage and failures
  release the reservation. Exhausted-limit tests seed an actually consumed
  limit; a newly created small limit alone is not the exhausted state.
- Policy/default/enforcement, cancellation, trailing slash, and root-path group:
  **52 passed**.
- Unknown/snapshot HTTP rejection group: **4 passed**.
- Frontend API-key flow, Automations, create-dialog and edit-dialog suites:
  **44 passed** across four files with `--maxWorkers=1`. An earlier default-worker
  run had one existing flow time out waiting for the initial Create key button;
  the complete serialized rerun passed without a product or timeout change.
- Frontend `node node_modules/@typescript/native/bin/tsc -b`: **passed**.
- ESLint on both edited frontend test files: **passed**.
- Strict OpenSpec validation: **change passed; 65 main specs passed**. All seven
  delta requirement blocks match the synced main specs; relative Markdown links
  are valid.
- `make lint`: **passed**, including architecture/cancellation/timing/settings
  checks, Ruff, and format checks.
- `uv run ty check`: **one unrelated existing error** at
  `tests/integration/test_proxy_chat_completions.py:109` (`dict` passed where
  `OpenAIErrorEnvelope` is expected). That test was already modified before this
  task; this change does not edit it. Scoped `ty check` over all seven changed
  Python files: **passed**.

The broad backend selection covers image schema/translation/pricing, Images
HTTP, model discovery, API keys, SDK compatibility and a Responses root-path
regression:

```sh
uv run pytest tests/unit/test_images_schemas.py \
  tests/unit/test_images_translation.py tests/unit/test_pricing.py \
  tests/integration/test_proxy_images.py tests/integration/test_v1_models.py \
  tests/e2e/test_openai_sdk_compat.py tests/integration/test_api_keys_api.py \
  tests/integration/test_proxy_responses.py::test_v1_responses_routes_under_root_path -q
```

The initial combined run passed **402 cases** with no failures before it was
interrupted after 7m41s because of repeated long waits between API tests. The
remaining cases were rerun in fresh processes and then batches of at most 20
with independent databases. Sixteen complete batches (**320 cases**) passed,
including every remaining Images, model-catalog and SDK case. Two final API-key
batches had SQLite teardown/setup errors after **17 additional passing cases**;
the 15 outstanding cases were submitted individually to fresh processes.
Final individual run: **14 passed; 1 teardown error**. The remaining error is
`test_update_limits_preserves_usage_committed_between_read_and_patch`: its
assertions pass, but fixture teardown exceeds 90 seconds with wedged SQLite
rollback/bridge shutdown writes. This unchanged test does not reference image
models. Follow-up recommendation: investigate the shared SQLite test lifecycle
separately; the long-lived aggregate invocation is not certified green.

Across the broad 754-case selection, **753 distinct cases have clean passing
results and one has a teardown error**. The unknown-model test was subsequently
expanded from one to four cases, all passing; the final scoped set therefore
has **756 distinct clean passes and one teardown error**. Repeated diagnostic
runs are not added to that count. The final Responses root-path rerun passed
with an aiosqlite worker/closed-event-loop warning, retained as another test
cleanup limitation.

Long-lived pytest processes exhibited wedged SQLite connection rollback/close
and bridge membership shutdown writes. One earlier combined remainder run
reported a teardown timeout after a Sunburst handoff test; that exact case and
all other image cases passed in fresh batches without a code change. Later
occurrences involved unchanged API-key tests. These observations establish a
shared SQLite test-lifecycle limitation, not a proven production root cause;
no database-lifecycle changes are included in this feature.

## Browser evidence

These capture the real dashboard UI served by Vite with synthetic API data;
they do not show a production environment. The after catalog was generated from
`SUPPORTED_IMAGE_MODELS`; the before catalog removes only the two 2.5 IDs. The
Playwright capture asserts search results contain four/six image entries and
both selected labels are visible. **2 browser cases passed**; captures were
visually inspected.

- [Before picker](./screenshots/before-picker.png)
- [After picker](./screenshots/after-picker.png)
- [Selected values](./screenshots/after-selection.png)

## Limits and assessment

No change-specific correctness issue remains. Feature requirements, affected
regressions, lint, scoped typing, frontend checks, and strict specs are verified.
Workspace-wide type checking and the aggregate backend invocation are not fully
green because of the unrelated diagnostic and SQLite lifecycle issue above.
No cloud CI/PR readiness is asserted. The implementation is ready for archive
with these documented verification limits; no deployment is included.

The implemented guarantee is local admission and faithful forwarding. Actual
upstream variant identity and account entitlement remain unverified. Explicit
`input_fidelity` and native mask semantics are not added. Pricing retains the
existing aggregate approximation, not modality-exact OpenAI invoicing. Stable
context documents these boundaries and an example request.

## Verified source snapshot

SHA-256 of scoped code/test files, to identify the reviewed working-tree state.
Unrelated pre-existing workspace edits are excluded from this manifest.

```text
9ac157c49ad23329a12977e6e27209a612f796b801dc203354373683eb673849  app/core/openai/images.py
8f69322e9f55f3dea4db67e9da4fb0baa5906325c11170117585c8363c563c0a  app/core/usage/pricing.py
02f495567e79887dcbbee04343da033e59d1d98dcf5136f0c053621707ee05dd  tests/integration/test_proxy_images.py
17271b960b7ee4731c20e0bb18848fd45935fdfe36e427a57f418958bdd15fc0  tests/integration/test_v1_models.py
c72577560471f1bdc545234586a0e7582ce4f69b49904c7a1590662a9acb8024  tests/e2e/test_openai_sdk_compat.py
ff90b6e22e0c0e675fbab4532ee696a720e43668c4ea2c1bf644f7316d02dd61  tests/unit/test_images_schemas.py
5417b81ba86db4ac1c4528aa8f5fcefff6eea64ca5efcdfa5561945b265604e5  tests/unit/test_pricing.py
88f1467c90705535ac5e6272cd32708f5833da9bdf18600165f8973be3dcb7fb  frontend/src/__integration__/api-keys-flow.test.tsx
30fcd341394e01948bc1f4f8e93c22a99e0bd28db55ba0f17cc32a611e6f08fa  frontend/src/__integration__/automations-flow.test.tsx
```

## Archive

Synced and archived as `2026-09-25-support-gpt-image-2-5-variants` after feature
verification. All 19 tasks are complete. No files were staged, committed, or
pushed, and no deployment/runtime state was changed.
