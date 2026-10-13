# Tasks

- [x] Add `gpt-6-luna` to the bootstrap catalog with endpoint metadata.
- [x] Extend model catalog compatibility requirements and endpoint regression coverage.
- [x] Record the earlier full catalog run (118 passed before the corrections; not a post-fix full-suite result).
- [x] Validate this change with `npx --yes @fission-ai/openspec@latest validate add-gpt-6-luna-catalog --strict`.
- [x] Restore all five endpoint-supported plans and cover eligibility with normalized plan spellings.
- [x] Leave the default service tier unset while retaining Fast; cover both discovery representations.
- [x] Split discovery scenarios between ordinary OpenAI-compatible and Codex-client endpoints.
- [x] Run focused affected regressions, scoped format/lint/type checks, and strict change validation.
- [x] Sync author-verified requirements and stable context to main specs for independent review of the combined diff.
- [x] Validate final documentation and record the integration-finalizer evidence handoff.
- [ ] Complete independent review of the corrected catalog diff and synced documentation.
- [ ] Archive only after independent verification (not in this worker).
