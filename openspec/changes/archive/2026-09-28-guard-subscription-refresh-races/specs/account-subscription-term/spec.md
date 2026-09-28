## MODIFIED Requirements

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
