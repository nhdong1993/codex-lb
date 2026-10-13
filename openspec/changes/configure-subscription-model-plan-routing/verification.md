# Author verification and documentation integration — 2026-10-11

## Status and scope

The original implementation's scoped author checks are recorded below. The
concurrent native HTTP dispatch correction was integrated and verified on
2026-10-13 (next section). **Independent review and archive remain pending.**
This record is not self-approval or a gate exception.
Both this change and `add-gpt-6-luna-catalog` are synced to their owning main
specs and stable context so independent review includes the combined diff.
No change is archived. The three-model Free PUT remains an unapplied
post-deployment example, not a feature-verification checkbox.

Evidence root: `/tmp/codex-model-plan-routing/`; logs below are relative to its
`verification/` directory. Sources are `backend-result.txt`,
`backend-author-completion.md`, `frontend-result.txt`,
`verification/frontend-completion.md`, `catalog-fix-result.txt`, and
`catalog-review-result.txt`. Commands run from `/home/dong01/codex-lb` unless
otherwise noted. Saved implementation checks are reused, not rerun by this
documentation continuation. Counts overlap and **must not be summed**.

## Integration verification — 2026-10-13

Run from `/home/dong01/codex-lb` against the shared working tree (other
changes were being edited concurrently; their files were not touched).

Fixes integrated in this pass:

- Final direct-send admission rechecks only configured models, using the
  effective policy and persisted account plan; unconfigured models keep their
  existing dispatch (a concurrently recorded plan-check rejection no longer
  turns into a 503 at dispatch).
- An invalid stored mapping no longer makes settings GET/PUT fail: settings
  show the still-valid entries (a missing value reads as empty) and a PUT
  replaces the stored value, while native routing keeps failing closed until
  then.
- Unit tests with stub repositories get an explicit empty policy snapshot via
  `model_admission.get_settings_cache` (autouse `tests/conftest.py` fixture);
  the dead dashboard additional-quota loader was removed and override tests
  now patch the live seam.
- Same-account retry regressions were corrected to the actual retry
  semantics (analysis below); head-pinned migration tests now pin
  `20261011_020000_add_model_plan_routing_policies`.

Retry analysis for `test_native_same_account_retry_rechecks_eligibility`:
stream 401 keeps the pre-existing immediate penalty for the real upstream 401
before the forced refresh, then the same-account resend is denied with 503 and
no further health write. A stream 502 connect-phase failure is a confirmed
pre-dispatch transport error, so the movable stream fails over instead of
retrying the same account: after a policy change it lands on the newly
eligible plus account (200); after a plan change no account is eligible and
the existing exhausted-retry 502 surfaces. In every case no dispatch reaches
an account the effective policy forbids. Mutation check: disabling the final
admission recheck fails 10 of the 12 cases (the two stream-502 cases are
governed by selection filtering).

| Command | Result |
| --- | --- |
| `uv run ruff check .` / `uv run ruff format --check .` | Passed (1217 files formatted) |
| `uv run python scripts/check_proxy_architecture.py` | Passed (`streaming/mixin.py` 1099, `load_balancer.py` 3015 lines) |
| `timeout 900 uv run ty check` | 2 diagnostics, both in files outside this change (`tests/integration/test_codeless_usage_limit_routes.py`, `tests/integration/test_proxy_transient_retry.py`) |
| Model Plan + settings suites (I1) | 150 passed |
| Bridge/WebSocket model admission (I2) | 96 passed |
| Isolated unit set (I3) | 2017 passed, 3 skipped, 2 failed (baseline API-key `usage_group` mock failures below) |
| Head-pinned migrations (I4) | 8 passed |
| Full unit suite (I6) | 9834 passed, 118 skipped, 18 failed; the 7 `test_settings_service.py` failures (bare rows with no stored mapping) were fixed and that file reran 15 passed; the other 11 are below |
| Other migration tests (I5) | 47 passed, 9 skipped, 10 failed (pre-existing, below); merge-test file rerun after its edit: 1 passed, 3 failed |
| `openspec validate configure-subscription-model-plan-routing --strict` | Valid |
| `openspec validate --specs` | 67 passed, 0 failed |

```sh
# I1
uv run pytest -q -p no:cacheprovider -n 4 tests/integration/test_model_plan_settings.py tests/integration/test_model_plan_dispatch.py tests/integration/test_model_plan_routing.py tests/integration/test_model_plan_source_isolation.py tests/integration/test_model_plan_migration.py tests/unit/test_model_plan_policy.py tests/integration/test_settings_api.py
# I2
uv run pytest -q -p no:cacheprovider -n 4 tests/integration/test_http_bridge_model_exclusion.py tests/integration/test_proxy_websocket_account_availability.py
# I3
uv run pytest -q -p no:cacheprovider -n 0 tests/unit/test_load_balancer.py tests/unit/test_proxy_utils.py tests/unit/test_hot_path_caches.py tests/unit/test_error_rate_weighting.py tests/unit/test_http_subscription_routing_hint.py tests/unit/test_proxy_load_balancer_refresh.py tests/unit/test_load_balancer_contract.py tests/unit/test_load_balancer_concurrency.py tests/unit/test_load_balancer_virtual_clock.py tests/unit/test_model_plan_policy.py
# I4
uv run pytest -q -p no:cacheprovider tests/integration/test_subscription_migration.py tests/integration/test_plan_check_migration.py tests/integration/test_reset_credit_outcome_migration.py tests/integration/test_source_ownership_migration.py tests/integration/test_source_ownership_history_migration.py tests/integration/test_model_source_websocket_migration.py tests/integration/test_new_account_warmup_migration.py tests/integration/test_model_plan_migration.py
# I6, then the settings-service rerun
uv run pytest -q -p no:cacheprovider -n 6 tests/unit
uv run pytest -q -p no:cacheprovider -n 0 tests/unit/test_settings_service.py
# I5
uv run pytest -q -p no:cacheprovider -n 4 tests/integration/test_migrations.py tests/integration/test_migration_serialization.py tests/integration/test_beta6_merge_migration.py tests/integration/test_key_group_migration.py tests/integration/test_migration_merge_overflow_transport.py
npx --yes @fission-ai/openspec@1.14.0 validate configure-subscription-model-plan-routing --strict
npx --yes @fission-ai/openspec@1.14.0 validate --specs
```

Remaining failures, not introduced by this change:

- I3: `test_regenerated_key_old_token_rejected_immediately` and
  `test_deactivated_key_rejected_immediately` (API-key mock rows lack
  `usage_group`), as recorded in the baseline limitations below.
- I6, outside this change's files: `test_websocket_upstream_transport_observability.py`
  (5, `_DummyFacade._should_penalize_stream_error` signature),
  `test_db_migrate.py` (2, legacy remap hits a duplicate `usage_group`
  column), `test_shutdown_drain_bounds.py` (1, trailing-slash inflight paths),
  `test_telemetry_consent.py` (1), plus the 2 I3 baseline failures.
- I5, `test_migrations.py` (7 legacy-bootstrap cases): `CircularDependencyError`
  inside the committed `20260921_010000_add_reset_credit_outcomes` batch
  migration, which runs before this change's revision.
- I5, `test_migration_merge_overflow_transport.py` (3 cases): its post-merge
  column check also rejected the committed non-null
  `limit_warmup_auto_enable_new_accounts` default; it now accepts known server
  defaults (including this change's `{}`), but the test still fails later
  because downgrading head to the overflow/transport merge also leaves
  `20260910_000000_add_api_key_usage_group` in `alembic_version`.

No PostgreSQL, full-repository, frontend, deployment or production check was
run in this pass.

## Backend saved checks

| ID | Result | Log |
| --- | --- | --- |
| B1: settings, policy, source isolation | 25 passed | `backend-settings-source-policy-final.log` |
| B2: product routing, selection contracts/caches | 60 passed | `backend-routing-selection-final.log` |
| B3: strengthened denial/file-owner assertions | 5 passed, 18 deselected | `backend-no-fallback-owner-verified.log` |
| B4: bridge/WebSocket warm admission | 26 passed, 70 deselected | `backend-warm-final.log` |
| B5: stricter WebSocket lifecycle rerun | 23 passed, 24 deselected | `backend-websocket-lifecycle-final.log` |
| B6: migration round trip | 1 passed | `backend-migration-roundtrip.log` |
| B7: prior finalizer warning check | 3 passed | `finalizer-warm-warning-check.log` |
| Scoped Ruff format/lint and ty | All passed, 17 owned files | `backend-{format,lint,typecheck}-final.log` |
| Owned-file whitespace | Passed | `backend-diff-check.log` |

Exact saved test commands:

```sh
# B1
.venv/bin/python -m pytest -q --timeout=45 --tb=short tests/integration/test_model_plan_settings.py tests/integration/test_model_plan_source_isolation.py tests/unit/test_model_plan_policy.py
# B2
.venv/bin/python -m pytest -q --timeout=45 --tb=short tests/integration/test_model_plan_routing.py tests/unit/test_load_balancer_contract.py tests/unit/test_hot_path_caches.py::test_account_selection_cache_reuses_inputs_and_invalidates_on_refresh tests/unit/test_hot_path_caches.py::test_different_models_get_different_cache_entries tests/unit/test_hot_path_caches.py::test_same_model_reuses_cache tests/unit/test_hot_path_caches.py::test_different_limit_names_get_different_cache_entries tests/unit/test_hot_path_caches.py::test_invalidate_clears_all_keyed_entries
# B3
.venv/bin/python -m pytest -q --timeout=45 --tb=short tests/integration/test_model_plan_routing.py -k no_paid_fallback
# B4
.venv/bin/python -m pytest -q --timeout=45 --tb=short tests/integration/test_http_bridge_model_exclusion.py tests/integration/test_proxy_websocket_account_availability.py -k 'policy or plan-change or (preserves_accepted_sibling and model) or (during_create_lease_wait and model)'
# B5
.venv/bin/python -m pytest -q --timeout=45 --tb=short -W error::pytest.PytestUnhandledThreadExceptionWarning tests/integration/test_proxy_websocket_account_availability.py -k 'preserves_accepted_sibling or during_create_lease_wait'
# B6
.venv/bin/python -m pytest -q --tb=short tests/integration/test_model_plan_migration.py
# B7
.venv/bin/python -m pytest -q --timeout=45 --tb=short -W error::pytest.PytestUnhandledThreadExceptionWarning tests/integration/test_proxy_websocket_account_availability.py::test_model_rejection_preserves_accepted_sibling

xargs .venv/bin/python -m ruff format --check < /tmp/codex-model-plan-routing/backend-owned-files.txt
xargs .venv/bin/python -m ruff check --output-format concise < /tmp/codex-model-plan-routing/backend-owned-files.txt
xargs .venv/bin/python -m ty check --output-format concise < /tmp/codex-model-plan-routing/backend-owned-files.txt
xargs git diff --check -- < /tmp/codex-model-plan-routing/backend-owned-files.txt
```

B1–B5 cover empty defaults, omission/null preservation, explicit clearing,
atomic validation, version/audit/guest contracts; the three explicitly
configured Free models at native product routes; source/unconfigured isolation;
API-key scope, entitlement, strict owners and retries; nonzero selection-cache
TTL, peer settings invalidation and persisted-plan revalidation; local sanitized
policy-evidence failures and warm accepted-sibling/resource settlement.

B4 emitted one aiosqlite closed-loop thread warning as well as the existing
Starlette deprecation. B5 and B7 treated thread warnings as errors and passed;
only the existing Starlette `BlockingPortal` deprecation remained. This is a
non-reproduction on stricter reruns, not a claimed fix to the earlier warning.

B6 used isolated SQLite and verified historical-row backfill, idempotency,
downgrade/re-upgrade and preserved unrelated settings. The single head was
`20261011_020000_add_model_plan_routing_policies`, with parent
`20261002_010000_add_credential_generation`; re-upgrade had no schema drift.
Earlier isolated CLI evidence is also saved, not repeated:

```sh
.venv/bin/codex-lb-db --db-url sqlite+aiosqlite:////tmp/codex-model-plan-routing/verification/migration.db upgrade head
.venv/bin/codex-lb-db --db-url sqlite+aiosqlite:////tmp/codex-model-plan-routing/verification/migration.db check
```

`db-upgrade.log` / `db-check.log`: expected current revision,
`migration_policy=ok`, `schema_drift=none`. **No PostgreSQL validation** was run.

## Frontend saved checks and screenshots

`frontend-tests.log`: **135 passed across 7 files**. From `frontend/`:

```sh
node node_modules/vitest/vitest.mjs run src/features/settings/components/model-plan-routing-settings.test.tsx src/features/settings/components/model-plan-routing-flow.test.tsx src/features/settings/components/routing-settings.test.tsx src/features/settings/components/settings-page.test.tsx src/features/settings/hooks/use-settings.test.ts src/features/settings/payload.test.ts src/features/settings/schemas.test.ts
node node_modules/@typescript/native/bin/tsc -b
node node_modules/eslint/bin/eslint.js screenshots/model-plan-routing.config.ts screenshots/model-plan-routing.spec.ts src/features/settings/components/model-plan-routing-settings.tsx src/features/settings/components/model-plan-routing-settings.test.tsx src/features/settings/components/model-plan-routing-flow.test.tsx src/features/settings/components/routing-settings.tsx src/features/settings/components/routing-settings.test.tsx src/features/settings/hooks/use-settings.ts src/features/settings/payload.ts src/features/settings/payload.test.ts src/features/settings/schemas.ts src/features/settings/schemas.test.ts src/test/mocks/factories.ts src/test/mocks/handlers.ts
node /home/dong01/.npm/_npx/83e71da30ae7cab2/node_modules/prettier/bin/prettier.cjs --check --print-width 120 screenshots/model-plan-routing.config.ts screenshots/model-plan-routing.spec.ts src/features/settings/components/model-plan-routing-settings.tsx src/features/settings/components/model-plan-routing-settings.test.tsx src/features/settings/components/model-plan-routing-flow.test.tsx
git diff --check -- src/features/settings src/i18n/locales src/test/mocks screenshots
```

Typecheck, scoped lint, scoped formatting and whitespace checks exited 0:
`frontend-{typecheck,lint,format,diff-check}.log`. Coverage includes native-only
picker filtering, saved absent IDs, no empty-plan saves, complete mapping
preservation, busy mutation/refetch, conflict draft reset and retryable ordinary
errors, empty defaults and English/Korean/Simplified Chinese warnings.

From the repository root, using isolated fixture-backed frontend copies:

```sh
SCREENSHOT_PHASE=before SCREENSHOT_FRONTEND_DIR=/tmp/codex-model-plan-routing/screenshots/before-frontend node frontend/node_modules/@playwright/test/cli.js test --config frontend/screenshots/model-plan-routing.config.ts --reporter=line
SCREENSHOT_PHASE=after SCREENSHOT_FRONTEND_DIR=/tmp/codex-model-plan-routing/screenshots/after-frontend node frontend/node_modules/@playwright/test/cli.js test --config frontend/screenshots/model-plan-routing.config.ts --reporter=line
```

`frontend-screenshots-{before,after}.log`: **4 cases passed** (1 before, 3 after),
**11 PNGs** in `/tmp/codex-model-plan-routing/screenshots/`: one before English
routing page, three after localized routing pages, six localized desktop/mobile
editor captures, and one empty English editor. Exact names, dimensions and
hashes are in `frontend-screenshots.json` and `frontend-completion.md`.
Browser assertions include 390px overflow checks; independent visual review
remains pending. No backend/database was used. Both screenshot dev processes
exited; the frontend author verified port 4249 was no longer listening.
Existing Vite and color-environment warnings were recorded by that author.
The full frontend suite and production build were not run.

## Separate catalog correction evidence

The initial catalog review returned `CHANGES_REQUIRED` for five missing plans,
a Fast default incorrectly set to priority, and an ordinary `/v1/models`
scenario promising Codex-only fields. The correction author addressed all
three; **independent review of those corrections remains pending**.

```sh
# Before correction: 5 expected regression failures (catalog-fix-red-tests.log)
env -u CODEX_LB_TEST_DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -p no:cacheprovider -q tests/unit/test_model_registry.py::test_bootstrap_gpt6_luna_endpoint_plans_remain_eligible tests/integration/test_v1_models.py::test_v1_models_uses_bootstrap_models_when_registry_not_populated tests/integration/test_v1_models.py::test_backend_codex_models_uses_bootstrap_upstream_metadata
# After correction: 29 passed, 93 deselected (catalog-fix-tests.log)
env -u CODEX_LB_TEST_DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -p no:cacheprovider -q tests/unit/test_model_registry.py tests/integration/test_v1_models.py -k "bootstrap or service_tier or metadata_retains_full_live_model_after_later_catalog_omits_it"
.venv/bin/ruff format --check app/core/openai/model_registry.py tests/unit/test_model_registry.py tests/integration/test_v1_models.py
.venv/bin/ruff check --no-cache app/core/openai/model_registry.py tests/unit/test_model_registry.py tests/integration/test_v1_models.py
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/ty check app/core/openai/model_registry.py tests/unit/test_model_registry.py tests/integration/test_v1_models.py
npx --yes @fission-ai/openspec@1.14.0 validate add-gpt-6-luna-catalog --strict
git diff --check -- app/core/openai/model_registry.py tests/unit/test_model_registry.py tests/integration/test_v1_models.py openspec/changes/add-gpt-6-luna-catalog/
.venv/bin/python -B /tmp/codex-model-plan-routing/verification/catalog-fix-evidence.py
```

All post-fix commands passed; static/evidence logs are
`catalog-fix-{format,lint,type,openspec,diff-check,evidence}.log`. Saved endpoint
evidence confirms **all 26 plans**, canonical/normalized eligibility, default
service tier `None` with Fast still available, null on Codex discovery versus
omission on ordinary OpenAI metadata, source separation and live precedence.
The earlier **118-pass** full catalog run (`catalog-review-tests.log`) predates
the fixes and is **not** a post-fix full-suite result.

The separate CLI catalog sync was already complete: 30 matching endpoint IDs,
no added or removed IDs. This continuation does not touch CLI config/auth/catalog
or production. Saved endpoint metadata may drift upstream in the future.

## Material baseline limitations — no author exceptions

- Superseded: the saved architecture run failed on `streaming/mixin.py`
  (1104 > 1100). The 2026-10-13 rerun passes (`mixin.py` 1099 lines,
  `load_balancer.py` 3015 lines) with no budget change; see the 2026-10-13
  integration section.
- The broader command below recorded **62 passed, 2 failed** in
  `backend-routing-cache-final.log`. API-key mock rows lack `usage_group` in
  `test_regenerated_key_old_token_rejected_immediately` and
  `test_deactivated_key_rejected_immediately`. Both failures reproduce from the
  baseline cwd (`parent-baseline-cache-tests.log`, exit 1). At the original author verification, relevant source/test
  files and the streaming mixin matched the supplied pre-task baseline. The
  concurrent correction now touches the mixin; these saved results do not
  establish its post-correction architecture status.

```sh
# Broader saved author run, repository cwd
.venv/bin/python -m pytest -q --timeout=45 --tb=short tests/integration/test_model_plan_routing.py tests/unit/test_load_balancer_contract.py tests/unit/test_hot_path_caches.py
# Actual saved baseline reproductions, cwd=/tmp/codex-model-plan-routing/baseline
/home/dong01/codex-lb/.venv/bin/python scripts/check_proxy_architecture.py
/home/dong01/codex-lb/.venv/bin/python -B -m pytest -p no:cacheprovider -q --tb=short tests/unit/test_hot_path_caches.py::test_regenerated_key_old_token_rejected_immediately tests/unit/test_hot_path_caches.py::test_deactivated_key_rejected_immediately
```

- `.venv/bin/python scripts/check_cancellation_safety.py`,
  `.venv/bin/python scripts/check_proxy_timing_seams.py`, and
  `.venv/bin/python scripts/check_settings_tiers.py` passed in
  `backend-architecture-final.log` (131/131 settings fields).
- The supplied older global `validate --specs --strict` baseline was **7 passed, 60
  warning-induced failures**, from long requirement paragraphs. The mandated
  nonstrict `validate --specs` baseline was **67/67 passed**, saved in
  `../specs-nonstrict-baseline.txt`. Unrelated requirements are not rewritten to
  hide those diagnostics. Final synced validation is recorded below.
- These failures are neither labeled fixed nor waived. The independent
  reviewer decides actual gate applicability. No full-repository, PostgreSQL,
  cloud/GitHub, production routing, rollout or readiness claim is made.

## Concurrent correction discovered during this documentation continuation

Historical record; the correction is integrated and verified in the
2026-10-13 integration section.

The independent reviewer reported a native HTTP final-send/same-account retry
gap: a selected account could dispatch after policy or persisted-plan changes
during admission waits/backoff. The separate `dispatch-fix-prompt.txt` records
that finding and assigns a corrective author; it explicitly leaves OpenSpec
with this documentation author. This is not a baseline exception or a resolved
finding. The final/new-request admission requirement now explicitly names
native streaming/compact sends and same-account retries as well as warm reuse.

`tests/integration/test_model_plan_dispatch.py` appeared after this continuation's
start snapshot. It was not written or run by this documentation author; it and
any subsequent corrective implementation are preserved. The saved 37-file
manifest still matched when that addition was detected, but does not cover the
new test. The correction's eventual `dispatch-fix-result.txt`, exact logs and
changed-file hashes must be integrated by the parent before a fresh independent
review. Earlier passing counts do not verify this concurrent delta. The final
task fingerprint captures the worktree at documentation handoff, not approval
or completion of the other worker's potentially ongoing changes.

## Final documentation checks and handoff

Only documentation is edited by this continuation. At entry, all **37** saved
backend/frontend/catalog code-and-test hashes matched
`verification/finalizer-code-hashes.json`. Final preservation checks compare
that manifest again and separately list concurrent dispatch-author changes;
results are saved in `documentation-preservation.log`. These external changes
are not attributed to the documentation author or silently discarded.
Both owning main specs and contexts preserve their pre-integration content;
only these changes' normative additions and stable context are appended.

Final documentation validation passed after sync:

| Command | Result | Log |
| --- | --- | --- |
| Routing change `validate ... --strict` | Passed, exit 0 | `documentation-routing-strict.log` |
| Catalog change `validate ... --strict` | Passed, exit 0 | `documentation-catalog-strict.log` |
| Main `validate --specs` | 67 passed, 0 failed; baseline warnings retained | `documentation-specs.log` |

Exact final commands:

```sh
npx --yes @fission-ai/openspec@latest validate configure-subscription-model-plan-routing --strict
npx --yes @fission-ai/openspec@latest validate add-gpt-6-luna-catalog --strict
npx --yes @fission-ai/openspec@latest validate --specs
git diff -- app/core/openai/model_registry.py tests/unit/test_model_registry.py tests/integration/test_v1_models.py > /tmp/codex-model-plan-routing/catalog-final.diff
git diff --check -- openspec/changes/configure-subscription-model-plan-routing openspec/changes/add-gpt-6-luna-catalog openspec/specs/account-routing openspec/specs/model-catalog-compat
.venv/bin/python /tmp/codex-model-plan-routing/verify-documentation-preservation.py
.venv/bin/python /tmp/codex-model-plan-routing/task_diff.py
```

Final validation logs: `documentation-routing-strict.log`,
`documentation-catalog-strict.log`, `documentation-specs.log`. The original
`catalog.diff` is retained unchanged; `catalog-final.diff` includes the three
catalog-file corrections. `task.diff`, `task-files.json` and
`task-fingerprint.txt` describe the final baseline-relative combined task.
The fingerprint is kept outside these documents to avoid self-reference.
`worker-result.txt` supplies the final fingerprint, changed documentation files,
checks and limitations to the read-only reviewer; the CLI's genuine
`turn.completed` event signals completion. No commit, push, deployment,
restart, live settings change, self-approval or archive was performed.
