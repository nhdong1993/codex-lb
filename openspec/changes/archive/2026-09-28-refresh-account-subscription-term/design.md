## Context

The reference implementation calls `/backend-api/subscriptions` with the stored access token, account ID and target-path headers using curl_cffi Chrome 136. A read-only probe using the configured account proxy succeeded without session cookies or a new login. The existing native Codex client returned a Cloudflare challenge for the same route.

## Decisions

- Add four nullable Account columns: successful active-until, checked-at, source fingerprint, and last attempt. Historical rows remain null and use the existing token fallback until refreshed.
- A leader-owned scheduler checks due paid accounts, including paused accounts, with at most three independent workers. Attempts are claimed atomically, rate-limited to once per 15 minutes per account, and never hold a DB session across network I/O. Shutdown cancels and awaits all workers.
- Hash the stored access credential, account identity and current plan to bind snapshots to their source. Replacement/rotation/plan changes invalidate old snapshots. Conditional writes reject changed/deleted accounts or superseded attempts.
- Use the standard route resolver with the internal Account.id. Route failure never falls through to direct access. Use direct access only when the resolver explicitly returns no route. No redirects, token refresh, status mutation, or proxy configuration changes.
- Accept the observed top-level response plus the reference's list/wrapped-list forms. Validate explicit subscription dates, plan and account identity where supplied. Explicit inactive/free results suppress token dates; malformed responses and transport errors preserve the last good snapshot.
- Summary GETs only read local state. Add nullable `subscription.source` (`subscriptions_api`, `id_token`) to distinguish checked live metadata from historical token fallback, retaining lastCheckedAt.
- All view modes use `xd xh` with floored values and no padding; a positive period below one hour is `0d 0h`. Unknown and elapsed states remain distinct.

## Risks / validation

Cloudflare or proxy failures can prevent refresh; source and last check make the age visible. Cookies/login automation are out of scope. Cover renewed deadlines at the dashboard API, malformed/inactive results, route refusal, credential races, partial failures, cancellation, migration round-trip, and shared-clock UI boundaries. Use only synthetic credentials in tests and screenshots.

## Rollout

Apply the additive migration before application startup. The scheduler backfills live metadata gradually; older replicas ignore new columns. No operator settings or manual production data edits are needed.
