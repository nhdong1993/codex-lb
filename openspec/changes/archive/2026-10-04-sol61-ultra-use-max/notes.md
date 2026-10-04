## Verification

- Read-only production checks on 2026-10-04 confirmed that all three catalog surfaces advertised `multi_agent_reasoning_effort: "xhigh"` for `gpt-6.1-sol`, with both max and ultra supported. The local pinned Codex catalog also retained xhigh.
- Before the implementation change, the new GPT-6.1 Sol API regression failed with `assert 'xhigh' == 'max'` at the native Codex catalog route.
- The implementation extends the existing exact model-name guard to `gpt-6.1-sol`; subscription ownership and both supported-effort guards remain in place.
- `uv run --frozen pytest -q tests/integration/test_codex_astra_ultra_catalog.py tests/integration/test_v1_models.py`: 113 passed, including all 42 Ultra policy cases across three public catalog routes.
- `uv run --frozen pytest -q tests/integration/test_proxy_responses.py`: 89 passed, including Ultra-to-max request forwarding coverage.
- Scoped Ruff lint and format checks passed; `git diff --check` passed.
- Strict OpenSpec validation passed for the change and all 67 main capabilities before synchronization. Archive synchronized the renamed requirement successfully; all 67 capabilities passed strict validation again afterwards.
- The requested pre-push full local CI command (`uv run pre-commit run local-ci --hook-stage manual --all-files`) stopped at frontend dependency installation because `bun` is not installed on this host. This is not a full-CI pass; the focused 202-test result and scoped lint/format checks above remain the available verification evidence.

## Activation

This change is verified locally; production has not been redeployed and client configuration has not been changed. After deployment, refresh pinned catalogs and start a new Codex session. Custom model sources continue to use their declared metadata, and explicit xhigh requests retain their existing semantics.
