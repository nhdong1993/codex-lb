## Purpose

Expose subscription terms checked through ChatGPT with a labeled stored-token fallback, without confusing them with token expiry or quota reset timing.

## Requirements

### Requirement: Account summaries expose recorded subscription term

The account summary API MUST expose nullable `subscription.activeUntil`, `subscription.lastCheckedAt` and `subscription.source`. Matching successful subscriptions API snapshots MUST take priority over stored ID-token claims. Without a matching snapshot, matching paid-plan ID-token claims MAY be used with source `id_token`. Live snapshots MUST use source `subscriptions_api` and their actual check timestamp. Snapshot identity MUST match the current stored credential, ChatGPT account and plan. Successful routine token rotation for the same identity and plan MUST preserve an already matching snapshot, including its original successful-check and attempt times. This preservation MUST include a matching snapshot committed after the rotation reads its source and before it writes the new credential; unmatched or concurrently replaced sources MUST NOT be authorized. Credential replacement, identity/plan changes and failed token rotation MUST NOT authorize reuse of an unmatched snapshot. Free/unknown current plans MUST NOT expose historical paid terms. Explicit inactive/free API results MUST suppress historical token deadlines. JWT expiry, quota reset and import time MUST NOT substitute for subscription dates. Credentials MUST NOT be exposed. Account-list and summary GETs MUST NOT issue subscription requests.

#### Scenario: Renewed subscription overrides an old token
- **WHEN** a matching Plus account has an ID-token deadline of September 4 and a successful subscriptions snapshot ending October 4
- **THEN** its list and detail summaries report October 4 with the API source and successful check time

#### Scenario: Source credentials changed
- **WHEN** account credentials, ChatGPT identity or plan differ from the successful snapshot source
- **THEN** that snapshot is ignored and only eligible current token metadata may be used

#### Scenario: API confirms inactivity
- **WHEN** the API explicitly reports an inactive or free subscription
- **THEN** the summary does not substitute a historical paid ID-token deadline
- **AND** account status and routing eligibility remain unchanged

#### Scenario: Routine token rotation keeps a verified term
- **WHEN** a paid account with a matching October 4 API deadline successfully rotates tokens without changing identity or plan
- **THEN** list and summary responses retain October 4 and the original API check time
- **AND** no extra subscription request is issued inside the daily interval

#### Scenario: Rotation cannot revive a replaced source
- **WHEN** token rotation changes identity or plan, loses its credential comparison, or starts with an unmatched subscription snapshot
- **THEN** it does not transfer that snapshot to the new credential

#### Scenario: First subscription snapshot commits during rotation
- **WHEN** the first matching subscription result commits after token rotation reads the account and before its guarded write
- **THEN** account-list and summary responses retain that result after the rotation
- **AND** original successful-check and daily-attempt timestamps remain unchanged

### Requirement: Subscription display distinguishes recorded term from live status

Account grid cards and selected-account details MUST show time remaining until the recorded subscription deadline, its date, and the available last-checked date. Unknown metadata MUST display an explicit unavailable state. An elapsed deadline MUST be labeled as an elapsed recorded period and MUST NOT change account status or routing eligibility. The UI MUST distinguish subscription time from access-token expiry and quota reset. Remaining time MUST refresh at least once per minute while the page is mounted.

#### Scenario: Future deadline counts down

- **WHEN** the recorded deadline is in the future
- **THEN** the UI shows the remaining duration and recorded end date
- **AND** the countdown updates without a page reload

#### Scenario: Recorded period has elapsed

- **WHEN** the stored deadline passes
- **THEN** the UI shows an elapsed recorded period without a negative duration or assertion that the live subscription expired

#### Scenario: Missing subscription metadata

- **WHEN** the deadline is unknown
- **THEN** the UI explicitly indicates no subscription-term data even if the access token has a known expiry

### Requirement: Compact recorded plan duration in account selectors

The original Detail selector MUST show plan time immediately beneath status. List, Grid and selected detail MUST render positive remaining durations as unpadded whole days and remaining whole hours with literal d/h suffixes, such as `5d 8h`; positive periods below an hour MUST display `0d 0h`. Unknown and elapsed states MUST remain distinct without changing account status. Source and last successful check MUST be visible in details and available in compact descriptions. All displays MUST use the shared minute clock without per-account upstream requests.

#### Scenario: Consistent days and hours
- **WHEN** a subscription has 5 days and 8 hours remaining
- **THEN** all views display `5d 8h` without leading zeroes

#### Scenario: Duration below one hour
- **WHEN** a subscription has 30 minutes remaining
- **THEN** it displays `0d 0h` until its deadline and then changes to the elapsed label

### Requirement: Background subscription refresh preserves ownership and availability

The system SHALL refresh paid account subscription terms using GET `/backend-api/subscriptions`, the account bearer token, ChatGPT account ID query/header, and both target-path headers. It SHALL use curl_cffi Chrome 136 for this endpoint and resolve the configured route with the internal account ID. Route failures SHALL NOT use direct fallback. Requests SHALL use TLS verification, a 20-second bound, and no redirects. Refresh SHALL include paused paid accounts and skip pending-deletion, deactivated and reauthentication-required accounts. It SHALL run under the existing leader lease with at most three workers, independently owned database sessions, and persisted 24-hour attempt throttling. Successful snapshots SHALL be shared through the database. Shutdown SHALL cancel and await workers. Snapshot writes SHALL reject superseded attempts and changed identities/credentials. Refresh failures SHALL preserve successful metadata and SHALL NOT rotate tokens or mutate account status, routing or plan. Invalid/missing dates SHALL NOT replace a valid snapshot unless an explicit inactive/free response confirms no paid term.

#### Scenario: One account fails
- **WHEN** one refresh returns a challenge or malformed data while another succeeds
- **THEN** the first account keeps its previous result and the second receives its new term

#### Scenario: Configuration cannot resolve a route
- **WHEN** an account-bound proxy or required default pool is unavailable
- **THEN** refresh makes no direct upstream request and leaves account health unchanged

#### Scenario: Concurrent replacement
- **WHEN** credentials are replaced while a request is in flight
- **THEN** its response cannot overwrite the replacement account's subscription metadata

#### Scenario: Historical rows
- **WHEN** the additive migration upgrades accounts created before live snapshots existed
- **THEN** existing credentials and status are preserved and snapshot columns remain unknown until refreshed

### Requirement: Operators can refresh one subscription manually

Authorized dashboard writers SHALL be able to refresh one eligible paid account through POST `/api/accounts/{account_id}/subscription/refresh`, with equivalent behavior for a trailing slash. The endpoint SHALL bypass the daily interval while enforcing a shared 30-second minimum interval between attempts, use the same route and conditional writes, and return the current account summary on success. It SHALL return 404 for an absent account, 409 for an ineligible, recently attempted or superseded account, and a sanitized 502 on upstream failure. It SHALL preserve the previous successful snapshot on failure. Account-list reads that began before a successful manual refresh completed MUST NOT subsequently replace that result with an older subscription. A manual refresh response MUST NOT replace subscription metadata for a different current Plan, ChatGPT account, email or workspace, or overwrite a newer recorded subscription check or credential refresh. The UI SHALL track pending refreshes independently for every account until each request settles, including failures. The UI SHALL offer refresh from List, Grid and selected Detail, disable it for readers and while pending, and update the subscription fields after success without opening a detail dialog.

#### Scenario: Daily automatic cadence
- **WHEN** a paid account was attempted less than 24 hours ago
- **THEN** automatic refresh does not issue another upstream request

#### Scenario: Manual refresh bypasses the daily interval
- **WHEN** an authorized operator presses Refresh subscription for an account checked earlier today
- **THEN** the backend performs one guarded refresh and returns the updated summary

#### Scenario: Manual refresh failure
- **WHEN** the manual upstream request fails
- **THEN** the API returns a safe upstream error, preserves the last successful term and does not expose response bodies or credentials

#### Scenario: Poll returns after successful manual refresh
- **WHEN** an account-list read starts during a manual refresh and returns old metadata after the refresh succeeds
- **THEN** the refreshed term remains visible
- **AND** later reads still update current account identity, policy, status and subscription normally

#### Scenario: Concurrent refreshes settle independently
- **WHEN** accounts A and B are refreshed and B settles while A remains in flight
- **THEN** A remains disabled and shows its pending indicator
- **AND** B becomes available whether its own request succeeded or failed

#### Scenario: Delayed response belongs to a replaced source
- **WHEN** account-list data already reflects a different Plan or account source while an older manual refresh response is delayed
- **THEN** receiving that response preserves the current source and its subscription metadata

#### Scenario: Delayed response is older than a current check
- **WHEN** the cache contains a newer subscription check or credential refresh than the delayed manual result
- **THEN** the newer metadata remains visible, including an explicit inactive result

#### Scenario: Matching fresh result preserves unrelated updates
- **WHEN** the account source still matches and a manual result is current
- **THEN** only its subscription fields are merged, preserving concurrent status, alias, routing and quota updates

### Requirement: Reset reconciliation preserves a newer compatible subscription term

When a reset-quota reconciliation result updates an account, the account list and dashboard MUST retain a subscription term from a successful refresh when that term belongs to the same account identity, plan, ChatGPT account and workspace, is not from an older credential refresh, and has a newer successful check timestamp than the reset result. The reconciliation state used by account and dashboard polls MUST retain the same merged subscription so an older in-flight response cannot restore the previous term. Quota, usage, status and reset-credit fields from the reset result MUST still be applied. Fresh polls started after the merge MUST remain authoritative, including newer inactive results and changed account sources.

#### Scenario: Delayed reset summary follows a successful refresh
- **WHEN** a reset summary containing an older subscription term arrives after a successful refresh containing a newer term for the same account
- **THEN** the account list and dashboard keep the newer term
- **AND** the reset summary's quota fields are applied

#### Scenario: Reconciliation state remains consistent after the merge
- **WHEN** an account or dashboard poll started before a reset or subscription merge completes after that merged result
- **THEN** it keeps the newer compatible subscription term
- **AND** it keeps the reconciled quota fields

#### Scenario: Different account identity is not transplanted
- **WHEN** a reset result belongs to a different plan, ChatGPT account, workspace or account identity, or records a newer credential refresh
- **THEN** the previously cached subscription term is not copied into that reset result

#### Scenario: A later authoritative response clears the term
- **WHEN** a reset summary or fresh poll contains a newer successful inactive subscription check
- **THEN** the account list and dashboard show no active term
- **AND** an earlier paid term is not restored from reconciliation state
