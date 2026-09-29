## Verification scope

The single added requirement and all six scenarios map to the dedicated native pricing entry, its alias, and existing shared accounting paths. Implementation follows the design without calculator, schema, routing, or configuration changes.

| Scenario | Evidence |
| --- | --- |
| Canonical/uppercase/suffixed identity and separate aggregates | `test_get_pricing_for_model_gpt_6_aliases`, `test_calculate_costs_includes_gpt_6_families_and_aliases` |
| Cached usage, tiers, log breakdowns and settlement | `test_gpt_6_cost_breakdown_by_tier_and_context_length`, `test_gpt_6_chat_completion_settles_cost_and_persists_log`, `test_request_logs_api_prices_gpt_6_families_and_aggregates` |
| Priced reservations exhaust the remaining quota before another upstream dispatch | `test_gpt_6_1_sol_cost_reservations_reject_exhausted_budget_before_upstream` |
| Long-context cached pricing | Pricing matrix plus log and settlement integration cases |
| Exact threshold and one token above | Pricing matrix at 272,000 and 272,001 input tokens |
| Unknown GPT-6.1 families | `test_get_pricing_for_model_does_not_guess_unknown_gpt_6_family` |

## Regression and checks

- Before the production edit, the new canonical-model test failed because `get_pricing_for_model("gpt-6.1-sol")` returned `None`.
- `uv run pytest tests/unit/test_pricing.py -q`: 161 passed.
- `uv run pytest tests/unit/test_api_keys_service.py -q`: 87 passed.
- Focused integration coverage: 12 settlement cases and one request-log API/aggregate case passed; the final reservation-admission run passed all five supported route variants. Total relevant coverage is 266 passing cases across these runs.
- Ruff check and format checks pass for all four changed Python files; `git diff --check` passes.
- Strict validation passes for this change and the affected `api-keys` main spec. The delta is synchronized exactly with the main spec.

## Existing repository limitations

Repository-wide `openspec validate --specs --strict` reports 51 valid and 15 invalid specs both before and after this change, with identical error records. Existing failures are in `chat-completions-compat`, `compatibility-tooling`, `database-backends`, `frontend-architecture`, `model-catalog-compat`, `outbound-http-clients`, `proxy-admission-control`, `proxy-runtime-observability`, `query-caching`, `responses-api-compat`, `sticky-session-operations`, `telemetry`, `upstream-proxy-routing`, `usage-error-metrics`, and `usage-refresh-policy`. They are unrelated to the added pricing requirement.

Reservation accounting retains existing integer-microdollar truncation and the cap at the remaining quota. The admission regression allows one microdollar of truncation for individual estimates while requiring the exact total reserved budget. Responses canonical and trailing-slash routes are covered; `/v1/chat/completions/` was verified to return the existing HTTP 405 and is excluded from successful pricing cases. Routing behavior is unchanged.

Historical costs and settled quotas are preserved. Production deployment and historical aggregate backfill are outside this change.

## Assessment

All six tasks are complete, the added requirement and six scenarios are covered, and the implementation matches the design. No change-specific critical issues or warnings remain. Archive is verified with the existing repository-wide validation failures recorded above.

## Review follow-up (2026-09-29)

A manual review and independent Codex review identified one P2 testing issue: if quota enforcement accidentally admitted the third concurrent request, the admission test awaited its response while the fake upstream waited for the release event in the subsequent `finally` block. This hid the failed quota assertion behind a deadlock.

The rejection request and pending-task cleanup now have explicit 10-second timeouts. An external temporary pytest plugin bypassed quota admission only for the third request to reproduce the original watchdog timeout. After the fix, the same injected regression raised the local `TimeoutError` and completed cleanup without firing the process watchdog.

The final combined pricing, API-key service, settlement, reservation-admission, and request-log API selection passed all 266 tests in 84.61 seconds. Ruff checks, format checks, and `git diff --check` passed. A second successful independent Codex review of the updated scoped change reported no actionable findings. The review changed only test timeouts and this verification record; no commit or deployment was performed.

## Final isolated review (2026-09-29)

A further independent review reported no new actionable findings. An independent Decimal oracle matched 6,272 pricing combinations, including aliases, service tiers, zero usage, full and excessive cached input, and the exact long-context boundary. Additional checks confirmed that null historical costs can use the calculated detail fallback while explicit stored costs, including zero, retain precedence.

Unrelated model-source websocket edits in the shared workspace temporarily prevented pytest collection. To verify this change independently, a temporary copy of HEAD `1556330d` received only the GPT-6.1 Sol pricing and test patch. The combined focused selection passed 264 tests in 67.33 seconds; the two image-model cases from unrelated workspace changes were excluded. The four Python files passed Ruff and format checks, the API-key spec passed strict validation, and the archived delta matched the main requirement exactly. This isolated code/test snapshot is the commit candidate.
