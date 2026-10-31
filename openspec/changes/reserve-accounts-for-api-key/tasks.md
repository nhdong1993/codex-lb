## 1. Schema and API key contract

- [x] 1.1 Alembic revision adding `accounts.reserved_api_key_id` (FK `ON DELETE SET NULL`, index)
- [x] 1.2 `reservedAccountIds` on create/update/response with 400/409 and one-transaction writes
- [x] 1.3 Merge reserved accounts into a scoped key's assignment
- [x] 1.4 Invalidate selection caches and close bridge sessions of newly reserved accounts

## 2. Routing

- [x] 2.1 Drop accounts reserved by another key from every selection-input load
- [x] 2.2 Prefer the key's reserved accounts, fall back to the pool, skip under `single_account`
- [x] 2.3 Pass the API key through opportunistic admission and codex control

## 3. Other key-scoped paths

- [x] 3.1 Reset-credit listing and redeem
- [x] 3.2 `/v1` warmup and keyed `warm-now`

## 4. Dashboard

- [x] 4.1 Reserved accounts picker in create/edit dialogs (en, ko, zh-CN)

## 5. Verification

- [x] 5.1 Integration tests for the API contract, migration, routing, reset-credit and warmup
- [x] 5.2 Unit tests for exclusion, preference, fallback and continuity fail-closed
- [x] 5.3 Dashboard tests and screenshots
- [x] 5.4 Update `docs/api-keys.md` and `docs/routing.md`
