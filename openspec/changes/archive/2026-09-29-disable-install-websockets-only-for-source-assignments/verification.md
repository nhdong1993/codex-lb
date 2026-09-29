# Verification

## Completeness

All four tasks are complete. The modified installer requirement is synchronized to `openspec/specs/api-key-dashboard/spec.md`; its context explains assignment policy, native-name collisions, examples, and when to export a fresh installer.

## Correctness

- The installer API derives the provider flag from the authenticated key's assigned source/account lists and sends only the boolean to the shared renderer.
- Eight integration cases execute the exported Bash script and inspect its resulting TOML/catalog: source-only (unrestricted and restricted), source/native-name collision, mixed assignments (unrestricted and restricted), account-only, and unassigned keys (unrestricted and restricted).
- These cases produced six assertion failures against the original implementation, then passed after the fix.
- Six platform/policy combinations rerun the installer over native, mixed, and source catalogs, verifying stable exported transport and exact model metadata. Windows scripts run under Linux PowerShell with only Windows ACL primitives replaced by the existing test harness.
- Existing tests cover authentication, private responses, backups, catalog failures, uninstall, and actual Codex CLI session resumption.

## Coherence

The implementation follows the design: the shared renderer owns the provider flag; catalog programs preserve per-model preferences without overriding it. No new setting, API response schema, or migration is introduced. Assignment changes require a new export as documented.

## Validation results

- `PATH=/tmp/codex-lb-pwsh:$PATH uv run pytest -q tests/unit/test_key_dashboard_install.py tests/integration/test_key_dashboard_api.py tests/integration/test_key_dashboard_install_catalog.py --tb=short`: **93 passed**.
- Focused `uv run ruff check` and `uv run ruff format --check` over all five changed Python files: passed.
- `git diff --check`: passed.
- Strict change validation: passed.
- `openspec validate --specs --strict`: **66 passed, 0 failed**, matching the clean baseline.

No critical issues or unresolved warnings. Native Windows ACL behavior was not exercised; it is unchanged.
