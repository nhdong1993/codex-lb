## ADDED Requirements

### Requirement: Subscription display exposes pending plan verification

Account summaries MUST expose a boolean `planCheckPending` derived from current, matching priority work. List, Grid and Detail MUST display an explicit verifying-plan state instead of a recorded countdown while verification is pending. Free and unknown plans MUST suppress historical paid countdowns. Priority verification MUST attempt a subscription check subject to the existing 30-second attempt throttle; an explicit inactive result MUST suppress historical deadlines even if the usage check fails. Successful routine token rotation MUST preserve eligible work, while credential replacement MUST invalidate it. Account GETs MUST remain free of upstream requests.

#### Scenario: Pending Free confirmation masks an old Plus deadline
- **WHEN** a paid account has a future deadline and pending priority verification
- **THEN** its account views display a verifying-plan label without a remaining duration

#### Scenario: Inactive subscription and failed usage check
- **WHEN** the subscription check reports inactive but usage verification fails
- **THEN** the stored inactive result continues to suppress the old deadline after priority attempts end

#### Scenario: Delayed refresh result cannot clear pending verification
- **WHEN** a manual subscription result arrives after the account list reports pending verification
- **THEN** merging the subscription result preserves the current pending flag

## MODIFIED Requirements

### Requirement: Subscription display distinguishes recorded term from live status

When plan verification is not pending, account grid cards and selected-account details MUST show time remaining until the recorded subscription deadline, its date, and the available last-checked date. Unknown metadata MUST display an explicit unavailable state. An elapsed deadline MUST be labeled as an elapsed recorded period and MUST NOT change account status or routing eligibility. The UI MUST distinguish subscription time from access-token expiry and quota reset. Remaining time MUST refresh at least once per minute while the page is mounted.

#### Scenario: Future deadline counts down

- **WHEN** a paid plan has a recorded future deadline and no pending plan verification
- **THEN** the UI shows the remaining duration and recorded end date
- **AND** the countdown updates without a page reload

#### Scenario: Recorded period has elapsed

- **WHEN** the stored deadline passes
- **THEN** the UI shows an elapsed recorded period without a negative duration or assertion that the live subscription expired

#### Scenario: Missing subscription metadata

- **WHEN** the deadline is unknown
- **THEN** the UI explicitly indicates no subscription-term data even if the access token has a known expiry

### Requirement: Compact recorded plan duration in account selectors

The original Detail selector MUST show subscription state immediately beneath status. List, Grid and selected detail MUST render positive remaining durations for paid plans without pending verification as unpadded whole days and remaining whole hours with literal d/h suffixes, such as `5d 8h`; positive periods below an hour MUST display `0d 0h`. Unknown and elapsed states MUST remain distinct without changing account status. Source and last successful check MUST be visible in details and available in compact descriptions. All displays MUST use the shared minute clock without per-account upstream requests.

#### Scenario: Consistent days and hours
- **WHEN** a paid subscription without pending plan verification has 5 days and 8 hours remaining
- **THEN** all views display `5d 8h` without leading zeroes

#### Scenario: Duration below one hour
- **WHEN** a paid subscription without pending plan verification has 30 minutes remaining
- **THEN** it displays `0d 0h` until its deadline and then changes to the elapsed label

### Requirement: Operators can refresh one subscription manually

Authorized dashboard writers SHALL be able to refresh one eligible paid account through POST `/api/accounts/{account_id}/subscription/refresh`, with equivalent behavior for a trailing slash. The endpoint SHALL bypass the daily interval while enforcing a shared 30-second minimum interval between attempts, use the same route and conditional writes, and return the current account summary on success. It SHALL return 404 for an absent account, 409 for an ineligible, recently attempted or superseded account, and a sanitized 502 on upstream failure. It SHALL preserve the previous successful snapshot on failure. Account-list reads that began before a successful manual refresh completed MUST NOT subsequently replace that result with an older subscription. A manual refresh response MUST NOT replace subscription metadata for a different current Plan, ChatGPT account, email or workspace, or overwrite a newer recorded subscription check or credential refresh. The UI SHALL track pending refreshes independently for every account until each request settles, including failures. The UI SHALL offer refresh from List, Grid and selected Detail, disable it for readers and while pending, and update the subscription fields after success without opening a detail dialog.

#### Scenario: Daily automatic cadence
- **WHEN** the routine daily scheduler visits a paid account attempted less than 24 hours ago
- **THEN** that routine refresh does not issue another upstream request

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
