# Accounts inventory charts

The charts provide an inventory overview alongside account management. Requirements live in [the delta spec](specs/frontend-architecture/spec.md).

Counts represent local account slots, including separate workspace credentials for the same login. They use the full accounts response, so searching for one account does not change fleet totals. A plan key is trimmed and lowercased before grouping; blank plans and unknown statuses have an explicit Unknown bucket. Re-auth required remains distinct from upstream deactivation.

For example, two Plus accounts (one active, one requiring re-authentication) and one deactivated Pro account show Plus 2/3, Pro 1/3; status groups each show 1/3. The center of both charts reads 3.

These charts summarize inventory, not available routing capacity or remaining quota. They add no network requests, dependencies, settings or stored counters. Loading and error states follow the page, while a successful empty response shows neutral rings and zero. Percentages are rounded for display; exact counts remain visible. Existing themes, languages and reduced-motion preferences apply.
