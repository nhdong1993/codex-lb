# Context: reserved accounts for an API key

## Purpose

Let an operator dedicate one or more upstream accounts to a single API key, for example a customer who pays for their own ChatGPT account. The key spends its own accounts first and only borrows from the shared pool when they are unusable; nobody else ever spends them.

## Decisions

- **One column on `accounts`.** `accounts.reserved_api_key_id` makes "at most one owner" a property of the schema. A flag on `api_key_accounts` would need a partial unique index and would not cover unscoped keys.
- **Exclusion after the cached selection-input load.** `drop_foreign_reserved` filters `accounts`, `continuity_owner_candidates` and `sticky_mutation_authority_account_ids` after `_load_selection_inputs`, at every caller. The API key is not part of the cache key, so installs without reservations keep the same cache hits and get the same object back.
- **`runtime_accounts` is not filtered.** It is the list of existing accounts: runtime-state pruning keeps cooldown/backoff of accounts in it, and continuity-owner errors use it to tell "owner deleted" from "owner outside policy". Filtering it would let other keys' traffic wipe the reserved account's cooldown and turn the fail-closed error into "no longer exists".
- **Preference is a pre-pass in the budget-safe wrapper**, not inside `logic.select_account`: the wrapper filters by budget and health before calling the strategy, so a preference inside the strategy would never see a draining reserved account. The pre-pass runs the same wrapper on the reserved states only, without backoff fallback and without usage-exhaustion errors; if it returns nothing the normal pass runs on all states.
- **`single_account` wins.** The operator pinned one account on purpose; the reservation still keeps other keys off the reserved account.
- **Conditional write.** `UPDATE … WHERE reserved_api_key_id IS NULL` then a count of rows owned by the key. A mismatch means another key won: `409 account_reserved_by_other_key` and the whole request rolls back. Unknown ids return `400 invalid_api_key_payload`, matching `assignedAccountIds`.
- **Scoped keys keep reserved ⊆ assigned**, so the many places that compute a scoped key's pool need no change.
- **After a write** the route invalidates the account-selection and routing caches and closes HTTP bridge sessions of the newly reserved accounts, so another key's open session cannot keep using them.
- **Response reads use a `lazy="raise"` relationship** loaded only by the dashboard loaders; the per-request API key load does not query reservations.

## Constraints and failure modes

- With `apiKeyAuthEnabled=false` every request is keyless, so reserved accounts are not used by anyone, including keyless `/v1` warmup. Release the reservations before disabling API key authentication.
- System tasks without an API key (quota-planner schedule, limit warmup, cache-isolation probe) still touch reserved accounts. Automation jobs scoped to all accounts skip them (they send real prompts); a job that selects a reserved account explicitly still runs on it. Display figures (pooled credits of other keys, `/v1/usage`, fleet) still count them.
- A disabled or expired key keeps its reservations; the accounts sit idle until an operator releases them.
- A sticky session that fell back to a pool account does not move back when the reserved account recovers; new sessions prefer it again.
- Closing bridge sessions on reservation is replica-local and also closes the owning key's own sessions on those accounts.
- Downgrading the migration drops the column and every reservation.

## Example

1. Accounts `acc-a` (customer-owned) and `acc-b` (shared). Admin sends `PATCH /api/api-keys/{K}` `{"reservedAccountIds": ["acc-a"]}` → 200 with `reservedAccountIds: ["acc-a"]`.
2. Admin tries `PATCH /api/api-keys/{J}` `{"reservedAccountIds": ["acc-a"]}` → `409 account_reserved_by_other_key`.
3. Requests with key K go to `acc-a` even at 80% usage while `acc-b` is at 5%. When `acc-a` hits its quota, K's requests go to `acc-b` until it resets.
4. Requests with key J only ever use `acc-b`.
