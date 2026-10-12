## MODIFIED Requirements

### Requirement: Overload rejections deprioritize the account for fresh selection

When upstream rejects a fresh admission for an account as overloaded (`server_is_overloaded` or `overloaded_error`), or returns a `server_error` matching the OpenAI processing-error signature defined below, the proxy MUST record the rejection, at the point where account health is written for it, in a replica-local per-account window that is independent of the transient error count and MUST NOT be reset by later successes on that account. When at least three rejections land inside a 120-second window, the proxy MUST deprioritize the account for fresh (unbound) selection for a bounded interval that grows exponentially with consecutive trips (60 seconds base, capped at 600 seconds, decaying to the base after 30 minutes without a trip); the level MUST saturate once the cap is reached so sustained overload cannot grow it without bound, and a trip while already deprioritized MUST NOT shorten the deadline. Deprioritization MUST be soft: selection first runs over the candidates not in overload backoff and, when the configured strategy and budget gates select none of them, runs again over the full candidate pool exactly as before. It MUST apply wherever a NEW account is chosen for a request — unbound selection and the sticky path's fresh binding, reallocation, or fallback pick — and MUST NOT apply to an established sticky owner, a continuity owner, or a hard-affinity owner. The proxy MUST log when the backoff engages. The failure classification, the failover decision, the existing transient error penalty, and the status and body returned to the client MUST remain unchanged.

#### Scenario: Warm sessions keep masking the generic error counters

- **GIVEN** account A is rejected as overloaded on fresh admissions while its
  bridge-reuse and sticky sessions keep succeeding
- **WHEN** three rejections arrive within 120 seconds
- **THEN** account A enters overload backoff even though its transient error
  count is zero
- **AND** fresh selection skips account A while another candidate is available

#### Scenario: Backoff never empties the pool

- **GIVEN** every selectable account is in overload backoff
- **WHEN** a fresh request selects an account
- **THEN** selection proceeds over the full candidate pool as if no account
  were backed off

#### Scenario: Backoff yields to an ineligible remainder

- **GIVEN** account A is in overload backoff and the configured strategy
  selects none of the other accounts (rate-limited, cooling down, in generic
  error backoff, or excluded by the strategy's budget gates)
- **WHEN** a fresh request selects an account
- **THEN** account A is selected rather than failing the request or reporting
  an account-cap error

#### Scenario: A previously unseen sticky key binds away from the backed-off account

- **GIVEN** account A is in overload backoff and account B is selectable
- **WHEN** a request carrying a session or prompt-cache key with no established
  owner selects an account
- **THEN** the new binding is made to account B
- **AND** a request whose key already maps to account A keeps using account A

#### Scenario: HTTP-status overload rejections keep their code

- **GIVEN** upstream answers a fresh admission with an HTTP 5xx whose body
  carries `server_is_overloaded`
- **WHEN** the same-account transient retries are exhausted and health is
  written after settlement
- **THEN** the health write carries `server_is_overloaded` rather than a
  collapsed `server_error`, so the rejection counts toward the account's
  overload window

#### Scenario: Recovery-probe reservation follows the selected pool

- **GIVEN** a fresh request whose selection ran over the overload-free
  candidates
- **WHEN** the selected account is a due recovery probe that needs a
  reservation
- **THEN** the reservation is taken from that same overload-free pool, so an
  older due probe skipped by the overload pass cannot invalidate the selection

#### Scenario: Pinned sessions are not denied by overload backoff

- **GIVEN** account A is in overload backoff
- **WHEN** a request hard-pinned to account A (continuity owner, sticky
  session, or file affinity) selects an account
- **THEN** the pin is honored exactly as before

#### Scenario: Consecutive trips back off longer, bounded

- **GIVEN** account A trips the window repeatedly with each burst starting when
  the previous backoff expires
- **WHEN** the backoff deadline is computed for each trip
- **THEN** the interval doubles from 60 seconds and never exceeds 600 seconds
- **AND** after 30 minutes without a trip the next trip returns to 60 seconds

#### Scenario: Non-overload transient errors do not feed the window

- **GIVEN** account A returns a transient `server_error` without the recognized OpenAI processing-error signature
- **WHEN** the proxy records account health
- **THEN** the generic transient error is recorded as before
- **AND** the overload window for account A is unchanged

#### Scenario: Recognized OpenAI processing failures count despite successes

- **GIVEN** an upstream error has code `server_error` and a message beginning with “An error occurred while processing your request. You can retry your request, or contact us through our help center at help.openai.com if the error persists.”
- **WHEN** the proxy records account health for HTTP errors or streamed terminal failures eligible for the existing account-health penalty
- **THEN** the failure MUST count once in the existing overload window at that health-write point
- **AND** when an API-key reservation exists, settlement MUST be confirmed before the health write, including terminal-stream closure by a startup probe; unconfirmed settlement MUST suppress the health write
- **AND** matching MUST ignore letter case and repeated whitespace, accept `https://help.openai.com` with an optional trailing slash, and permit an optional trailing request-ID sentence
- **AND** intervening successful requests MUST NOT clear this window
- **AND** the original error code and message returned to the client MUST remain unchanged

#### Scenario: Generic and lookalike messages do not qualify

- **GIVEN** a `server_error` has no message, a generic internal-error message, only a help-center domain mention, or a lookalike help-center domain
- **WHEN** the proxy records account health
- **THEN** it MUST NOT add that failure to the overload window
- **AND** a different error code carrying the processing-error message MUST NOT qualify through this message rule

### Requirement: Upstream overload rejections back off and then isolate the account

The balancer SHALL keep a replica-local sliding window of upstream overload admission rejections (`server_is_overloaded`, `overloaded_error`) and message-qualified OpenAI `server_error` failures per account that successes do not reset. When the window trips, the account SHALL enter a bounded, exponentially growing **soft backoff** during which fresh unbound selection and fresh sticky bindings prefer other candidates. When the backoff level reaches the isolation trip level, the account SHALL instead be **isolated** for `CODEX_LB_PROXY_OVERLOAD_ISOLATION_SECONDS` (default 1800; `0` disables isolation and keeps the soft backoff only). While isolated, established soft sticky owners MAY be released as specified by `sticky-session-operations`. In both stages the account MUST be dropped from a candidate pool only while at least one other candidate remains, and the configured strategy MUST judge eligibility of the remaining pool: when it rejects every overload-free candidate, selection MUST fall back to the full pool exactly as before. The backoff level MUST NOT decay while the account is backed off or isolated; it decays only after a quiet interval measured from the later of the last trip and the backoff deadline. Hard continuity owners MUST NOT be moved by either stage. The balancer MUST emit a warning when isolation engages, naming the account, level and isolation interval.

#### Scenario: Sustained rejection escalates from soft backoff to isolation

- **GIVEN** an account whose overload window has tripped twice (soft backoff)
- **WHEN** it trips a third time
- **THEN** the account is isolated for the configured isolation interval instead of the next soft interval
- **AND** a warning `Account overload isolation engaged` is logged with the level and interval

#### Scenario: Isolation is disabled by a zero interval

- **GIVEN** `CODEX_LB_PROXY_OVERLOAD_ISOLATION_SECONDS=0`
- **WHEN** an account's overload window trips at or beyond the isolation level
- **THEN** it receives the capped soft backoff interval and is never marked isolated

#### Scenario: Leaving isolation while still rejected re-isolates

- **GIVEN** an account whose isolation deadline just passed
- **WHEN** its overload window trips again within the decay interval
- **THEN** its level has not decayed and the account is isolated again

#### Scenario: A lone candidate is never held out

- **GIVEN** the only selectable account is isolated
- **WHEN** a request selects an account
- **THEN** the isolated account is selected rather than failing with `No available accounts`
