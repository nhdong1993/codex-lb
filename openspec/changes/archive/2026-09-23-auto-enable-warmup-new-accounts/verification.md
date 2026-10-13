# Verification

## Completeness and correctness

The enrollment requirement and all four scenarios are implemented. Both
`AccountsService.import_account` and `OauthService._persist_tokens` initialize
the new account's existing warm-up field. Repository credential replacement
retains the stored field; no schema or scheduler changes are needed.

Coverage includes:

- Browser and device OAuth creating an enrolled account, visible through the
  dashboard account listing.
- Auth.json import creating an enrolled account with the global switch either
  enabled or disabled, without changing that switch.
- Device reauthentication, targeted browser reauthentication, and reimport
  retaining both enabled and disabled preferences while replacing credentials.
- Existing warm-up tests enforcing the global switch, safe account states,
  staggered idle eligibility, cooldown, and durable deduplication.

The four initial new-account cases failed against the old implementation at
the `limitWarmupEnabled` assertion before the two service changes were applied.

## Validation

- `uv run --frozen pytest -q tests/integration/test_accounts_api.py tests/integration/test_oauth_flow.py tests/unit/test_limit_warmup.py`: **148 passed**.
- Ruff lint and format checks on both services and both integration test files:
  passed.
- `git diff --check`: passed.
- Strict OpenSpec validation of `auto-enable-warmup-new-accounts`: passed.
- Strict whole-spec validation: **50 passed, 15 failed** due to pre-existing
  content. Comparison against tracked HEAD found no new error by capability,
  requirement title, and error message. HEAD has 16 failing capabilities; the
  unrelated account-routing edits already in the workspace resolve one. The
  three existing usage-refresh-policy errors concern older requirements
  missing SHALL/MUST; inserting the new requirement only shifts their indices.

## Coherence and operational scope

Implementation follows the design: enrollment happens at the authentication
entry points, operator preferences survive replacement, and the global default
remains disabled. Main requirements and context are synchronized. No new setting,
migration, dashboard UI, or immediate upstream probe was introduced.

No findings block this change. Repository-wide spec validation remains limited
by the existing errors recorded above. This verifies the local implementation;
production requires deployment of the updated application.
