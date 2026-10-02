## ADDED Requirements

### Requirement: Priority work remains fenced during replacement contention

Priority enqueue and downgrade-evidence mutations MUST serialize with credential replacement before checking their source. A statement that began while replacement was uncommitted MUST NOT recreate old pending work or observations after replacement commits.

#### Scenario: Delayed enqueue waits behind reauthentication
- **WHEN** reauthentication holds the account transaction and deletes old pending work while an old enqueue is waiting
- **THEN** the enqueue cannot reinsert work or suppress routing for the repaired account

#### Scenario: Delayed observation waits behind reauthentication
- **WHEN** replacement deletes downgrade observations while an old priority observation is waiting
- **THEN** the old observation cannot count toward confirmation under the new credentials

### Requirement: New Free evidence reopens remaining priority work

A first confirmable Free observation after completed priority verification MUST reopen work if the original window and attempt budget permit it. Reopening MUST preserve the original expiry and used attempts, schedule a follow-up after 15 seconds, and fence completion from the previous generation. Exhausted work MUST NOT restart within the same window.

#### Scenario: Paid confirmation precedes new Free evidence
- **WHEN** a check completes with a paid sample and a first Free sample arrives within its window with attempts remaining
- **THEN** verification becomes pending again and a follow-up can confirm Free

### Requirement: Priority cancellation settles shared authentication work

When priority verification has entered a shared OAuth refresh, cancellation or timeout MUST wait for that refresh's exchange and guarded persistence to settle before returning. Cancellation MUST still propagate after settlement. Shared refresh MUST NOT be cancelled because a priority caller stops, and ordinary request callers MUST retain their existing cancellation behavior.

#### Scenario: Shutdown during OAuth refresh
- **WHEN** a usage 401 starts OAuth refresh and the priority scheduler stops during the exchange
- **THEN** shutdown waits for token/status persistence before closing resources and no priority-owned refresh remains running

#### Scenario: Priority waiter shares an exchange with a request
- **WHEN** a priority waiter is cancelled while an ordinary request joins the same refresh
- **THEN** the request can receive the refresh result and the priority waiter propagates cancellation after settlement
