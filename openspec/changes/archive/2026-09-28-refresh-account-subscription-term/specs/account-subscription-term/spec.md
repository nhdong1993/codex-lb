## MODIFIED Requirements

### Requirement: Account summaries expose recorded subscription term

The account summary API MUST expose nullable `subscription.activeUntil`, `subscription.lastCheckedAt` and `subscription.source`. Matching successful subscriptions API snapshots MUST take priority over stored ID-token claims. Without a matching snapshot, matching paid-plan ID-token claims MAY be used with source `id_token`. Live snapshots MUST use source `subscriptions_api` and their actual check timestamp. Snapshot identity MUST match the current stored credential, ChatGPT account and plan. Free/unknown current plans MUST NOT expose historical paid terms. Explicit inactive/free API results MUST suppress historical token deadlines. JWT expiry, quota reset and import time MUST NOT substitute for subscription dates. Credentials MUST NOT be exposed. Account-list and summary GETs MUST NOT issue subscription requests.

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

### Requirement: Compact recorded plan duration in account selectors

The original Detail selector MUST show plan time immediately beneath status. List, Grid and selected detail MUST render positive remaining durations as unpadded whole days and remaining whole hours with literal d/h suffixes, such as `5d 8h`; positive periods below an hour MUST display `0d 0h`. Unknown and elapsed states MUST remain distinct without changing account status. Source and last successful check MUST be visible in details and available in compact descriptions. All displays MUST use the shared minute clock without per-account upstream requests.

#### Scenario: Consistent days and hours
- **WHEN** a subscription has 5 days and 8 hours remaining
- **THEN** all views display `5d 8h` without leading zeroes

#### Scenario: Duration below one hour
- **WHEN** a subscription has 30 minutes remaining
- **THEN** it displays `0d 0h` until its deadline and then changes to the elapsed label

## ADDED Requirements

### Requirement: Background subscription refresh preserves ownership and availability

The system SHALL refresh paid account subscription terms using GET `/backend-api/subscriptions`, the account bearer token, ChatGPT account ID query/header, and both target-path headers. It SHALL use curl_cffi Chrome 136 for this endpoint and resolve the configured route with the internal account ID. Route failures SHALL NOT use direct fallback. Requests SHALL use TLS verification, a 20-second bound, and no redirects. Refresh SHALL include paused paid accounts and skip pending-deletion, deactivated and reauthentication-required accounts. It SHALL run under the existing leader lease with at most three workers, independently owned database sessions, and persisted 15-minute attempt throttling. Successful snapshots SHALL be shared through the database. Shutdown SHALL cancel and await workers. Snapshot writes SHALL reject superseded attempts and changed identities/credentials. Refresh failures SHALL preserve successful metadata and SHALL NOT rotate tokens or mutate account status, routing or plan. Invalid/missing dates SHALL NOT replace a valid snapshot unless an explicit inactive/free response confirms no paid term.

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
