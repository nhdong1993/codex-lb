## MODIFIED Requirements

### Requirement: Operators can probe an account to wake the upstream limiter

The dashboard MUST expose an admin-only endpoint that sends a single minimal `responses.create` directly to upstream pinned to one account, bypassing load-balancer scoring, then immediately refreshes that account's `/wham/usage` snapshot. The probe `responses.create` MUST omit `max_output_tokens`, which the Codex endpoint does not support. The endpoint MUST surface the before/after usage and account status so operators can verify whether the upstream limiter re-evaluated.

#### Scenario: Probe wakes the upstream limiter and refreshes usage state
- **WHEN** an operator POSTs to `/api/accounts/{account_id}/probe`
- **AND** the account is `active`, `rate_limited`, or `quota_exceeded`
- **THEN** the service sends one `responses.create` request directly to `{upstream_base_url}/codex/responses` with `stream=true`, `store=false`, and no `max_output_tokens` field
- **AND** the service triggers an immediate `UsageUpdater.refresh_accounts` for that account
- **AND** the response body carries `probe_status_code`, `primary_used_percent_before`, `primary_used_percent_after`, `secondary_used_percent_before`, `secondary_used_percent_after`, `account_status_before`, `account_status_after`

#### Scenario: Probe rejects hard-blocked accounts
- **WHEN** an operator POSTs to `/api/accounts/{account_id}/probe`
- **AND** the account `status` is `paused` or `deactivated`
- **THEN** the endpoint responds `409` with code `account_not_probable`
- **AND** no upstream request is sent

#### Scenario: Dashboard exposes Force probe only for probeable statuses

- **WHEN** the dashboard renders account actions for an account
- **AND** the account `status` is `active`, `rate_limited`, or `quota_exceeded`
- **THEN** the dashboard exposes a Force probe action for that account
- **AND** invoking the action refreshes the account list, dashboard overview, projections, and that account's trends
- **BUT WHEN** the account `status` is `paused` or `deactivated`
- **THEN** the Force probe action is disabled or hidden

#### Scenario: Probe returns 404 for unknown account
- **WHEN** an operator POSTs to `/api/accounts/{account_id}/probe`
- **AND** no account with that id exists
- **THEN** the endpoint responds `404` with code `account_not_found`

### Requirement: Credit-backed secondary quota remains usable

When account status is derived from persisted usage snapshots, an exhausted secondary-window usage percentage MUST NOT by itself mark an account `quota_exceeded` if the governing usage snapshot reports usable credit-backed capacity. Usable credit-backed capacity is present only when `credits_unlimited` is true or `credits_balance` is positive. A bare `credits_has` value of true with `credits_balance` missing or zero is not usable credit-backed capacity and MUST NOT override exhausted secondary-window usage.

This credit-aware interpretation MUST be shared by proxy account selection and account/dashboard summary status mapping so an account selected as usable by the proxy is not simultaneously displayed as `quota_exceeded` in the operator summary. Exhausted primary-window usage MUST still take precedence as `rate_limited` whenever the secondary window is not itself blocking (below `100%` or covered by usable credit-backed capacity); when both windows are exhausted without usable credit-backed capacity the account is `quota_exceeded` with the secondary reset guard. Paused or deactivated accounts MUST NOT be reactivated solely because a usage snapshot reports usable credits. This requirement does not make local long-window usage snapshots authoritative for foreground proxy selection when account-routing treats them as advisory.

#### Scenario: Secondary quota exhausted with credits remains active

- **GIVEN** an account is persisted as `quota_exceeded`
- **AND** its governing secondary-window usage reports `used_percent >= 100`
- **AND** the same usage snapshot reports usable credit-backed capacity
- **WHEN** proxy selection or account-summary mapping derives the effective status
- **THEN** the effective status is `active`

#### Scenario: Secondary quota exhausted with only a bare has-credits flag stays quota-exceeded

- **GIVEN** an account is persisted as `quota_exceeded`
- **AND** its governing secondary-window usage reports `used_percent >= 100`
- **AND** the newest usage sample with credit metadata reports `credits_has = true`
- **AND** `credits_unlimited` is false
- **AND** `credits_balance` is missing or zero
- **WHEN** proxy selection or account-summary mapping derives the effective status
- **THEN** the effective status remains `quota_exceeded`
- **AND** the reset guard points at the secondary reset time

#### Scenario: Exhausted primary window keeps rate-limit precedence

- **GIVEN** an account has usable credit-backed capacity in its usage snapshot
- **AND** its primary-window usage reports `used_percent >= 100`
- **WHEN** proxy selection or account-summary mapping derives the effective status
- **THEN** the effective status is `rate_limited`

#### Scenario: Both windows exhausted without spendable credits stay quota-exceeded

- **GIVEN** an account's primary-window usage reports `used_percent >= 100`
- **AND** its secondary-window usage reports `used_percent >= 100`
- **AND** the newest usage sample with credit metadata reports no unlimited credits and no positive balance, or carries no credit metadata at all
- **WHEN** account-summary mapping derives the effective status with status inference from usage enabled
- **THEN** the effective status is `quota_exceeded`
- **AND** the reset guard points at the secondary reset time

#### Scenario: Operator-disabled states are preserved

- **GIVEN** an account is `paused` or `deactivated`
- **AND** its usage snapshot reports usable credit-backed capacity
- **WHEN** proxy selection or account-summary mapping derives the effective status
- **THEN** the account remains `paused` or `deactivated`

### Requirement: Credit-backed usage remains selectable after quota windows fill

When deriving effective account status from upstream usage samples, the system MUST treat the latest spendable credit metadata as an override for secondary quota-derived blocking state. If the latest usage sample with credit metadata reports `credits_unlimited = true` or `credits_balance > 0`, then secondary quota windows at `100%` MUST NOT by themselves keep the account `quota_exceeded`. If the latest usage sample reports only `credits_has = true` with `credits_unlimited = false` and `credits_balance` missing or zero, that sample MUST NOT override secondary quota exhaustion. Primary-window exhaustion MUST keep `rate_limited` precedence over an unexhausted or credit-covered secondary window when status inference from usage is enabled.

This override MUST NOT reactivate accounts that are explicitly `paused` or
`deactivated`. When multiple usage samples carry credit metadata, the newest
sample by `recorded_at` MUST be used.

#### Scenario: Credit-backed weekly account remains selectable

- **GIVEN** an account is otherwise routable
- **AND** its weekly usage window reports `used_percent = 100`
- **AND** its primary usage window is below `100`
- **AND** the newest usage sample with credit metadata reports a positive credit balance
- **WHEN** the load balancer derives account state
- **THEN** the derived status remains `active`
- **AND** the account remains eligible for selection

#### Scenario: Persisted weekly quota block with only a bare has-credits flag is not selectable

- **GIVEN** an account is persisted as `quota_exceeded`
- **AND** its weekly usage window reports `used_percent = 100`
- **AND** its primary usage window is below `100`
- **AND** the newest usage sample with credit metadata reports `credits_has = true`
- **AND** `credits_unlimited` is false
- **AND** `credits_balance` is missing or zero
- **WHEN** the load balancer derives account state
- **THEN** the derived status remains `quota_exceeded`
- **AND** the account is not eligible for selection until that quota window resets or a later snapshot reports spendable credits

#### Scenario: Credit-backed account remains rate-limited when primary window is exhausted

- **GIVEN** an account is otherwise routable
- **AND** its primary usage window reports `used_percent = 100`
- **AND** the newest usage sample with credit metadata reports a positive credit balance
- **WHEN** the load balancer derives account state
- **THEN** the derived status is `rate_limited`
- **AND** the reset guard points at the primary reset time

#### Scenario: Newer zero-credit sample removes the override

- **GIVEN** an older usage sample reports available credits
- **AND** a newer usage sample reports no unlimited credits and zero credit balance
- **WHEN** quota status is derived from usage
- **THEN** the newer zero-credit sample is authoritative
- **AND** a persisted full long-window quota block is not cleared by a bare `credits_has` flag

#### Scenario: Paused account is not reactivated by credits

- **GIVEN** an account is paused
- **AND** its newest usage sample reports available credits
- **WHEN** quota status is derived from usage
- **THEN** the account remains paused

### Requirement: Streaming usage-limit failures request an immediate coalesced usage refresh

When an upstream stream fails with `usage_limit_reached` or an `upstream_error` envelope whose upstream-authored message proves usage exhaustion, the proxy MUST request an immediate usage refresh for the failing account in addition to
marking it rate limited. The refresh MUST run as a tracked background task that
never blocks or alters the response, MUST load the account from a fresh
background-session row rather than the request's `Account` instance, and MUST
bypass the usage freshness gate. Usage refreshes run on two per-account
singleflight lanes: the background scheduler and forced refreshes use the bare
account key with caller-bound sessions, while the rate-limit payload, fleet and
request-triggered refreshes use the owned-session key. A requested refresh MUST
join a refresh already in flight on either lane rather than starting a third
concurrent upstream fetch, and concurrent requests for the same account MUST
share a single in-flight owned-session refresh without queueing a successor
fetch. Repeated requests for the same account within a fixed 15 second window
MUST be dropped. The request MUST be
skipped when usage refresh is disabled, when the account is in usage-refresh auth
cooldown, or when the fresh row is missing, `paused`, `reauth_required`, or
`deactivated`. When the requested (or joined) refresh writes usage rows it MUST
invalidate the account selection cache, so the next selection observes the new
usage evidence without waiting out the cache TTL. Plain `rate_limit_exceeded`
throttling and quota error codes MUST NOT request a refresh.

#### Scenario: A 429 storm produces a single upstream fetch

- **GIVEN** twenty concurrent streams on one account fail upstream with `usage_limit_reached`
- **WHEN** each failure requests a usage refresh
- **THEN** at most one upstream usage fetch runs for that account
- **AND** every failure's response is unaffected by the refresh

#### Scenario: A request joins the scheduler's in-flight refresh

- **GIVEN** the background scheduler is refreshing an account on the bare account singleflight key
- **WHEN** a stream on that account fails with `usage_limit_reached`
- **THEN** the requested refresh waits on the scheduler's in-flight refresh and records its outcome
- **AND** no additional upstream fetch starts

#### Scenario: A request joins an in-flight owned-session refresh

- **GIVEN** the rate-limit payload path or another request is refreshing an account on the owned-session singleflight key
- **WHEN** a stream on that account fails with `usage_limit_reached`
- **THEN** the requested refresh joins that in-flight refresh
- **AND** no additional upstream fetch starts

#### Scenario: Repeats inside the debounce window are dropped

- **GIVEN** a usage refresh was requested for an account less than 15 seconds ago
- **WHEN** another stream on that account fails with `usage_limit_reached`
- **THEN** no new refresh is requested
- **AND** a failure after the window elapses requests a refresh again

#### Scenario: The pool reports usage exhaustion on the next selection

- **GIVEN** the last selectable account's stream fails upstream with `usage_limit_reached`
- **AND** a selection between the rate-limit mark and the refresh's row write repopulated the selection cache without usage evidence
- **AND** the requested refresh writes a usage row at or above 100 % with its reset time
- **WHEN** the next request selects an account
- **THEN** the written row has invalidated the selection cache
- **AND** selection fails with the structured `usage_limit_reached` failure carrying that `resets_at`
- **AND** it does not wait for the next scheduled refresh interval or the selection cache TTL

#### Scenario: The request never mutates the streaming request's account

- **GIVEN** a stream fails with `usage_limit_reached` for an `Account` bound to the request session
- **WHEN** the requested refresh runs
- **THEN** it reads and updates only the fresh background-session row
- **AND** the request's `Account` instance is neither read nor written by the refresh

#### Scenario: Ineligible rows and disabled refresh are skipped

- **GIVEN** usage refresh is disabled, or the account is in auth cooldown, or its fresh row is missing, `paused`, `reauth_required`, or `deactivated`
- **WHEN** a stream on that account fails with `usage_limit_reached`
- **THEN** no upstream usage fetch runs

#### Scenario: A code-less usage-limit frame requests the same refresh

- **WHEN** an upstream stream fails without an explicit code and its message asserts that the usage limit has been reached
- **THEN** the proxy requests the same coalesced usage refresh as for `usage_limit_reached`
- **AND** the existing eligibility, debounce, and singleflight rules remain in effect
