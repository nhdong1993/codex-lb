# Tasks

## 1. Run-time default model selection

- [x] 1.1 Export ordered model preferences (enforced model, else allowlist order) from the install-script route and render them into Bash and PowerShell setup data.
- [x] 1.2 Make the Python and PowerShell catalog programs skip preferences absent from the retained catalog, fall back to the first retained model, and report skipped preferences on stderr.
- [x] 1.3 Cover skipped hidden/retired preferences, all-missing fallback, unchanged empty-catalog failure, and route-level preference export in tests.

## 2. Documentation and verification

- [x] 2.1 Sync the requirement and update `api-key-dashboard/context.md` with the selection rule and an example; run strict OpenSpec validation.
- [x] 2.2 Run the installer unit suite, key-dashboard API/catalog integration suites and focused lint; record results.

## Verification Notes

- `uv run pytest tests/unit/test_key_dashboard_install.py`: 41 passed, 22 skipped (PowerShell runtime unavailable on this host; PowerShell paths need CI or a pwsh host).
- `uv run pytest tests/integration/test_key_dashboard_api.py tests/integration/test_key_dashboard_install_catalog.py`: 35 passed (two pre-existing aiosqlite ResourceWarnings).
- `uv run ruff check` / `ruff format --check` on touched files: clean.
- `openspec validate skip-unavailable-installer-models --strict` and `openspec validate --specs --strict` for `api-key-dashboard`: valid.
