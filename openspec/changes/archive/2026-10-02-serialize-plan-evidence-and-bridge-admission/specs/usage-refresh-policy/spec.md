## ADDED Requirements

### Requirement: Delayed first-Free enqueue cannot supersede consumed evidence

A first-Free enqueue MUST create or reopen priority work only while shared evidence for the same account identity still contains exactly one pending Free observation. Enqueue MUST serialize with priority evidence mutations before checking this condition. An enqueue delayed until confirmation has advanced or consumed that evidence MUST NOT change the confirming generation or prevent the confirmed plan from being persisted.

#### Scenario: Confirmation overtakes first-Free enqueue
- **WHEN** an ordinary refresh commits its first Free observation and its enqueue resumes after a priority refresh consumes the second Free observation but before saving the plan
- **THEN** the enqueue does not replace the priority generation
- **AND** the account summary reports Free after confirmation, including when only one attempt remains

#### Scenario: Enqueue waits behind evidence mutation
- **WHEN** a priority refresh holds the account transaction while advancing or clearing Free evidence and an older first-Free enqueue waits for it
- **THEN** the enqueue rechecks committed evidence and does not recreate or reopen work from the consumed first sample
