# Checked subscription term

The [subscription-term requirements](spec.md) let operators compare remaining paid periods on the Accounts List, Grid and selected detail. These dates are informational and do not drive routing, renewal, or account health.

## Source and interpretation

The preferred source is a successful `GET https://chatgpt.com/backend-api/subscriptions?account_id=...` snapshot. The mapper exposes its explicit `active_until` as `subscription.activeUntil`, the time of the successful request as `lastCheckedAt`, and `source: subscriptions_api`. A leader-owned background scheduler refreshes paid accounts (including paused accounts) at most once per 24 hours, with three workers. Listing accounts never waits for these requests. Snapshots and attempt times live in nullable Account columns, shared by all replicas.

The HTTP client follows the reference `tool_vip_v2` implementation: curl_cffi Chrome 136, existing bearer credential, ChatGPT account query/header and both target-path headers. A probe confirmed that the configured proxy plus this profile could obtain the renewed term using an existing Codex access token, without browser cookies or reauthentication. The normal Codex transport still received a Cloudflare challenge on this endpoint, which is why this transport is scoped to subscriptions. The route resolver receives the internal account ID; the ChatGPT ID is used only for the upstream request. Route failure never falls back to direct access.

If no matching successful snapshot exists, the stored ID token's `chatgpt_subscription_active_until` and `chatgpt_subscription_last_checked` remain available with `source: id_token`. The UI labels this as saved-token fallback. A hash binds each API snapshot to its access credential, ChatGPT identity and current plan; changed source data invalidates a historical snapshot. Snapshot writes also compare the source and attempt time, so an in-flight response cannot overwrite a replaced account.

Automatic renewal can extend a subscription after either snapshot was checked. Elapsed dates are therefore labeled “Recorded period elapsed”; they do not disable an account or assert a payment failure. A challenge, timeout, invalid payload or unavailable proxy preserves the last successful snapshot and its original check time. An explicit inactive/free API result records an unknown paid term and suppresses the historical token deadline without changing account status, plan or routing.

## Missing and historical data

Null, absent, malformed, and out-of-range values remain unknown independently of the rest of the token. A token's `exp`, quota reset, and local refresh timestamp are not substitutes. A current free/unknown plan, or a mismatch between the token's plan and current stored plan, suppresses old paid-term dates. Upstream ISO datetimes without an offset are interpreted as UTC, matching these token claims; dashboard responses emit explicit offsets.

## Example

Given an ID-token deadline of September 4 and a subscriptions response with `active_until: 2026-10-04T04:36:34Z`, Accounts displays October 4 after the successful refresh. At September 28, 20:36:34 UTC, it displays `5d 8h`. The source reads “ChatGPT subscription check” and the actual check time remains visible. Access-token expiry stays separate under Token Status. If no deadline exists, the subscription panel displays “No data”.

## Account overview

Accounts defaults to its original Detail mode, with account selection on the left and statistics/charts inline on the right. The additional List and Grid overviews are remembered under `codex-lb-accounts-view-mode`, independently of the Dashboard view. All three modes retain search, status filters and sorting. List and Grid render at most 24 accounts per page using existing summary data; selecting an overview account opens management in a dialog. Only the inline selected account or open dialog requests trend/reset-credit data. One page-level timer updates subscription countdowns each minute.

The frontend accepts both historical naive UTC `lastRefreshAt` and current offset-bearing values so a rolling deployment can serve either backend version. Older summaries without a `subscription` field remain valid and display an unknown term.

## Compact presentation

The original Detail selector shows remaining time beneath the status badge, and List has a dedicated duration column. All modes use unpadded whole days and hours with literal d/h suffixes: `18d 8h`, or `0d 0h` during a positive period shorter than an hour. The elapsed label remains distinct. The shared minute clock keeps all rows aligned. Source, recorded end date, last check and renewal limitations remain in compact descriptions; Grid and selected details keep the full visible presentation.

For example, at September 27, 2026 12:00 UTC, a deadline of October 15, 2026 20:00 UTC reads `18d 8h` under Active. A missing deadline reads “No data” even if an access-token expiry exists; a passed deadline reads “Elapsed” without changing Active or routing eligibility.

## Operations

The additive migration leaves historical snapshot columns null; the scheduler fills them gradually after startup. Request/session cleanup is bounded and owned by the application lifespan. It skips deleted, deactivated and reauthentication-required accounts, uses no new settings, and does not rotate credentials. Persistent failures are throttled by the attempt clock while successful data remains available. A different account identity, replaced credential or plan must be refreshed before its prior API result can be reused. Successful routine token rotation for the same identity and plan transfers an already valid snapshot binding to the new access credential in the token compare-and-set transaction; it preserves the term, successful-check timestamp and daily attempt clock. A stale, unmatched snapshot is never revived by rotation.

## Manual refresh

The refresh icon beside the subscription term is available in List, Grid and the selected Detail panel. It requests one account through POST `/api/accounts/{account_id}/subscription/refresh`. It bypasses the daily cadence and uses the same account proxy, credential binding and guarded persistence. The existing attempt clock provides a shared 30-second minimum interval to suppress repeated clicks and concurrent automatic/manual attempts. A failed request keeps the prior term, source and check time and shows an error. This does not refresh credentials or consume reset credits.

For example, an operator can refresh an account checked an hour ago immediately after renewal. Its new term appears without waiting until tomorrow. Read-only viewers can inspect the recorded term but cannot trigger the write action.

## Refresh consistency

Auth Guardian may rotate credentials after twelve hours of age, while subscription attempts remain daily. The token rotation transaction carries an already matching snapshot forward for unchanged ChatGPT account, user, workspace and plan. Arbitrary credential replacement and identity/plan changes still invalidate the old binding. The source guard is evaluated again in the database update so a concurrent change cannot authorize a snapshot read from another source. No extra subscription request or invented check time is needed.

For example, an account checked at 08:00 with an October 4 deadline retains that deadline after routine token rotation at 20:00, including an 08:00 last-check label. An explicit inactive result also survives rotation, so old ID-token dates remain suppressed. Existing invalid snapshots continue to wait for the regular or manual refresh.

On the dashboard, successful manual refresh cancels older account-list reads before merging its subscription fields. Later polls remain authoritative, including identity, plan and status changes. Pending account IDs come from the mutation cache, so refreshing A and B keeps both controls disabled; when B succeeds or fails, A stays pending until its own request settles. This state follows the account across List, Grid and the selected Detail panel without a separate component timer or request counter.

## Concurrent snapshot and response ownership

Snapshot transfer during token rotation checks the database's current successful-check field and fingerprint against the computed old source fingerprint in the token UPDATE. The prior ORM read supplies source identity and credential values, not permission to reuse its snapshot. This matters during first refresh or after a credential replacement: a matching API result can commit between the read and write, and that newly valid result should survive the rotation. Concurrent account, user, workspace, plan or access-credential changes still fail the SQL source guard; a replaced refresh credential still fails the token CAS. No request is added to the daily cadence.

Manual response merging also checks the current public account source (Plan, ChatGPT account, email and workspace), plus lastRefreshAt and subscription.lastCheckedAt. When workspace IDs exist, labels can change without changing the source; legacy slots use their label. A delayed response cannot replace a newer subscription check, including a checked null deadline. Missing incoming timestamps do not displace known current timestamps. Unrelated status, alias, policy and quota values remain those of the current cache. Later list reads remain authoritative.

For example, a Plus refresh response may be delayed while the list observes a downgrade to Free. Receiving the old response leaves Free with no paid term rather than restoring the Plus deadline. If two valid API checks arrive out of order for the same account, the later successful-check timestamp wins. These guards use existing public metadata and do not send token material to the browser.

Reset-quota reconciliation and manual subscription refreshes can overlap. The reset response remains authoritative for quota, usage, status, and reset-credit fields, while a newer compatible subscription check remains authoritative for the recorded plan term. The frontend carries that merged subscription through both account and dashboard caches and the in-memory reconciliation state, so a delayed reset summary or an older in-flight poll cannot revert it.

For example, if a reset summary still reports an ID-token deadline of September 4 but a manual subscriptions API refresh has just recorded October 4, the UI applies the reset quota values and continues to display October 4. A later poll can update health or usage fields, but it cannot restore September 4 unless the account identity or plan changes and a new authoritative snapshot is accepted.

## Pending plan verification

`planCheckPending` is a top-level account summary flag derived from current, matching priority work. List, Grid and Detail replace the historical remaining duration with “Verifying plan” while it is true. Free and unknown plans never display a historical paid countdown. Subscription source and last-check information remain available; reading a summary does not issue upstream requests. Manual-refresh merging changes subscription metadata only, so a delayed response cannot clear the current pending flag.

For example, a stored Plus deadline can still say `1d 21h` even after the real subscription is inactive. A model rejection or first eligible Free usage observation requests priority work and masks that countdown. The worker attempts a subscription check under the existing 30-second throttle, independently of usage confirmation. If all attempts fail, the pending flag expires and the last successful recorded metadata remains; this is not proof of active entitlement. An explicit inactive subscription response continues to suppress the old deadline after the check window closes.
