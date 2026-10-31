## Why

Operators want to give one API key its own upstream account: that key should use the account first, and no other key (and no keyless request) should ever spend it. Account assignment (`api_key_accounts`) only narrows what a key may use; it never stops an unscoped key from using the same account, so a dedicated account is not possible today.

## What Changes

- Add `accounts.reserved_api_key_id` (nullable FK to `api_keys.id`, `ON DELETE SET NULL`, indexed). One account is reserved by at most one key.
- `POST/PATCH /api/api-keys` accept `reservedAccountIds`; every API key response returns it (sorted). Unknown ids return `400 invalid_api_key_payload`; an account already reserved by another key returns `409 account_reserved_by_other_key` and nothing in the request is committed. For a scoped key, reserved accounts are merged into its assigned accounts. Deleting a key releases its accounts.
- Account selection drops accounts reserved by another key (or by any key, for keyless requests) from fresh selection, continuity owners and sticky authority. A key prefers its own reserved accounts while they are usable and falls back to its normal pool when they are exhausted, cooling down, paused or deactivated. `single_account` routing still wins over the preference.
- Reset-credit listing/redeem, `/v1` warmup and keyed `warm-now` honor the same rule.
- Dashboard: a "Reserved accounts (preferred)" picker in the API key create/edit dialogs.

No new settings. Without any reservation, routing is unchanged.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `api-keys`: reserved accounts on the API key contract, reset-credit and warmup scope.
- `account-routing`: reserved accounts are exclusive to their key and preferred by it.

## Impact

- Schema: one Alembic revision adding `accounts.reserved_api_key_id` with FK and index.
- Code: `app/db/models.py`, `app/modules/api_keys/*`, `app/modules/proxy/load_balancer.py`, `app/modules/proxy/_load_balancer/{reserved_accounts,sticky_selection,opportunistic_admission}.py`, `app/core/balancer/logic.py`, proxy compact/retry/codex-control/warmup/reset-credit paths, `app/modules/quota_planner/warmup.py`, dashboard API key dialogs and locales.
- API: `reservedAccountIds` on `/api/api-keys` requests and responses; new `409 account_reserved_by_other_key`.
