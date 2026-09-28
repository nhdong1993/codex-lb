# Verification: account-plan-filter-routing-controls

Verified September 28, 2026.

| Dimension | Result |
| --- | --- |
| Completeness | Plan filter, List quick routing, shared badges, daily subscription cadence and manual refresh implemented |
| Correctness | Covered through dashboard API, frontend mutation/component tests and browser interactions |
| Coherence | Reuses the existing routing mutation, subscription transport and guarded persistence; no new schema or settings |

## Evidence

- `tests/integration/test_subscription_refresh.py` covers 24-hour scheduling, manual refresh before the daily deadline, canonical/trailing-slash routes, missing accounts, write permissions, failure preservation and repeated-click throttling. Existing credential replacement, cancellation and partial-failure coverage continues to pass after moving shared refresh work into `subscription_service.py`.
- Subscription backend suites: **52 passed**.
- Frontend account list, item, overview row, subscription, details, page, mutations and request-log suites: **112 passed**. These cover combined filters across view changes, keyboard/click Burn First controls, independent refresh, read-only actions and success/error cache behavior.
- Browser scenarios: **3 passed** for Detail/List/Grid at 1440, 1024, 768 and 390 pixels. The List scenario verifies saved Burn First state in both directions, a refresh request without opening management, plan filtering, sorting and compact row heights.
- Frontend lint, TypeScript and production build passed. Backend targeted Ruff/type checks and cancellation/proxy architecture checks passed.
- Strict OpenSpec change validation and all **66 main specs** passed. `git diff --check` passed.

Before images remain in `../2026-09-28-refresh-account-subscription-term/evidence/` after archive. Updated synthetic screenshots are under this change's `evidence/`, including List desktop/mobile and dark-theme review. All screenshot and browser mutation data is synthetic.

## Scope and limitations

Automatic attempts now occur once per 24 hours. Manual refresh bypasses that interval with a shared 30-second minimum between attempts. Burn First on replaces the existing policy with `burn_first`; off sets `normal`. Badge styles preserve raw plan labels and do not add backend capacity or eligibility rules for Promax.

No production API mutation, migration, commit, push or deployment was performed for this change. Validation used the focused backend and frontend suites rather than the full repository test suite. No critical findings or known requirement deviations remain; ready for archive.
