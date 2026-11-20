## 1. Selection and admission

- [x] 1.1 `plan_exempt_api_key_id` in `_load_selection_inputs` and the cache key; owner reload via `load_inputs_for_key`
- [x] 1.2 `plan_exempt` through `select_account`, opportunistic admission and `_select_account_with_budget`
- [x] 1.3 Admission reads the reservation with the plan; `api_key_id` at every caller; policy-only recheck helper

## 2. Continuations and bridge sends

- [x] 2.1 Lookup-miss continuation disables the exemption on stream, compact and direct WebSocket
- [x] 2.2 Bridge prewarm, pre-created, auth and security-work replays recheck after their waits

## 3. Verification

- [x] 3.1 Unit, route and bridge tests
- [x] 3.2 Docs
