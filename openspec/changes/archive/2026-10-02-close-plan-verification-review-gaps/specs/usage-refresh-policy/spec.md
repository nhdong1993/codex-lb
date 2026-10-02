## ADDED Requirements

### Requirement: New Free evidence survives in-flight paid completion

When a separate refresh records a first confirmable Free observation after an in-flight check's paid sample, the system MUST preserve a pending follow-up while attempts and the original request window remain. The older completion MUST NOT clear that pending state. The check's own first Free observation MUST retain delayed retry behavior without resetting its budget.

#### Scenario: Free arrives before paid check completion
- **WHEN** a paid check has processed its sample and another refresh observes Free before that check completes
- **THEN** the account summary remains pending and a subsequent agreeing Free sample can confirm the downgrade
- **AND** the original expiry and used attempts are preserved

#### Scenario: Priority check itself observes first Free
- **WHEN** priority verification records the first Free observation
- **THEN** it schedules a delayed follow-up using its remaining attempts
