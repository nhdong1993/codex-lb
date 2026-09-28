## Approach

- Keep plan and status filtering local to the already loaded account summaries so list/detail/grid remain fast and account GETs do not fan out upstream requests.
- Reuse one plan badge class map for request logs and account components. Unknown plans use the neutral free style; Prolite and Promax receive stable dedicated colors.
- Render the List row as an row with separate native buttons for opening details, toggling Burn First and refreshing subscription. The actions are siblings and stop propagation, preserves row selection, and uses the existing routing-policy mutation.
- Keep subscription refresh ownership in the existing repository/scheduler. The persisted attempt clock becomes one day for automatic work; a manual request uses the same guarded claim/write path with an explicit manual flag and a shared 30-second minimum interval.
- The manual refresh endpoint returns the refreshed account summary and never exposes credentials or upstream response bodies. It uses the same route resolver and curl_cffi subscription client as background refresh.

## Validation

Cover plan filtering, badge classes, quick routing toggles, daily throttling, manual refresh success/error handling, and stale-write protection. Run focused frontend tests, backend tests, lint, typecheck and production build.
