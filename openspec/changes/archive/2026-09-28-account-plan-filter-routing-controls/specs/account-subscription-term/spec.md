## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Operators can refresh one subscription manually

Authorized dashboard writers SHALL be able to refresh one eligible paid account through POST `/api/accounts/{account_id}/subscription/refresh`, with equivalent behavior for a trailing slash. The endpoint SHALL bypass the daily interval while enforcing a shared 30-second minimum interval between attempts, use the same route and conditional writes, and return the current account summary on success. It SHALL return 404 for an absent account, 409 for an ineligible, recently attempted or superseded account, and a sanitized 502 on upstream failure. It SHALL preserve the previous successful snapshot on failure. The UI SHALL offer refresh from List, Grid and selected Detail, disable it for readers and while pending, and update the subscription fields after success without opening a detail dialog.


#### Scenario: Daily automatic cadence
- **WHEN** a paid account was attempted less than 24 hours ago
- **THEN** automatic refresh does not issue another upstream request

#### Scenario: Manual refresh bypasses the daily interval
- **WHEN** an authorized operator presses Refresh subscription for an account checked earlier today
- **THEN** the backend performs one guarded refresh and returns the updated summary

#### Scenario: Manual refresh failure
- **WHEN** the manual upstream request fails
- **THEN** the API returns a safe upstream error, preserves the last successful term and does not expose response bodies or credentials
