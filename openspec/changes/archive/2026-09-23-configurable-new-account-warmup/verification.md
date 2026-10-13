# Verification

## Requirement coverage

- Settings model, repository, service, API response/update contracts, and audit
  change tracking carry `limit_warmup_auto_enable_new_accounts`.
- New OAuth/import accounts read the existing settings cache at credential
  persistence. Repository replacement preserves stored preferences.
- Integration cases cover both enrollment defaults for import, device OAuth,
  browser OAuth, targeted reauth, and credential replacement. Settings round-trip
  coverage checks unrelated updates, the independent global switch, and already
  enrolled accounts.
- The accessible switch remains editable while global warm-up is off, and follows
  the parent's busy/write-access state. English, Korean, and Chinese copy explain
  its scope. Frontend tests cover both toggle directions and save/refetch.
- Migration upgrade, downgrade, re-upgrade, retained account preferences, and a
  previously disabled global switch are covered on an isolated SQLite database.
  The prior reset-credit migration test follows the updated single head.

## Validation

- Backend account API, OAuth, settings API, and limit warm-up suites: 225 passed.
- Isolated `codex-lb-db upgrade head` followed by `codex-lb-db check`: passed,
  `migration_policy=ok`, `schema_drift=none`.
- New migration and preceding reset-credit migration tests: one passed each.
- Frontend routing/settings schema tests: 83 passed. Settings hook/payload tests:
  18 passed. TypeScript build check and focused ESLint checks passed.
- Focused Python Ruff lint/format checks and `git diff --check`: passed.
- Strict OpenSpec change validation: passed. Whole-spec strict validation remains
  at 50 passed / 15 failed; failure messages are unchanged from the pre-change
  report. The change does not add a new spec validation error.
- Browser rendering reviewed using mocked dashboard API data:
  [before](screenshots/before.png) and [after](screenshots/after.png).

## Design coherence and rollout

The implementation retains the global off-by-default traffic gate and adds no
environment variable or new navigation entry. Migration initializes the settings
value only; account opt-outs are retained. Main specs and context describe the
setting and rollout semantics. Production deployment is not part of this change.

All requirements, scenarios, and implementation tasks were verified. No findings
block this change; the repository-wide pre-existing spec errors remain as noted.
