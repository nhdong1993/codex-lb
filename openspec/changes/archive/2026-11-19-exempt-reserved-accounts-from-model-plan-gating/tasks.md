## 1. Selection

- [x] 1.1 `ModelRegistry.service_tier_plan_restriction` separates tier-specific Plan data from the model Plan fallback
- [x] 1.2 Plan exemption predicate and `plan_exempt_api_key_id` in the model filters
- [x] 1.3 `_load_selection_inputs` takes `plan_exempt_api_key_id` (cache key) and the owner reload goes through `load_inputs_for_key` on every selection path

## 2. HTTP bridge

- [x] 2.1 Bridge reuse applies the exemption from the current request's reserved accounts (keyless: none)

## 3. Verification

- [x] 3.1 Unit tests: owner selection, fallback, other keys/keyless baseline errors, continuity early return, Spark mixed pools, opportunistic admission, reservation changes between loads, catalog/tier/ultrafast/suppressed guards, cache entries
- [x] 3.2 Integration tests through `/backend-api/codex/responses` and the HTTP bridge
- [x] 3.3 Update `docs/routing.md`
