## ADDED Requirements

### Requirement: Newly authenticated accounts automatically enroll in limit warm-up

When successful browser OAuth, device-code OAuth, or auth.json import creates a new local account, the system MUST persist `limit_warmup_enabled=true`. Credential replacement or reauthentication of an existing local account MUST preserve that account's stored warm-up preference, including an explicit disabled value. Enrollment MUST NOT change global warm-up settings or send a warm-up request during authentication or import; background warm-up MUST continue to enforce its global switch, account state, quota eligibility, scheduling, and durable deduplication checks.

#### Scenario: OAuth creates an enrolled account

- **WHEN** browser or device-code OAuth successfully creates a new local account
- **THEN** the account is persisted with limit warm-up enabled
- **AND** dashboard account listings return `limitWarmupEnabled: true`

#### Scenario: Auth import creates an enrolled account

- **WHEN** an authorized auth.json import creates a new local account
- **THEN** the account is persisted with limit warm-up enabled
- **AND** dashboard account listings return `limitWarmupEnabled: true`

#### Scenario: Credential replacement preserves account preferences

- **GIVEN** an existing account has limit warm-up explicitly enabled or disabled
- **WHEN** OAuth reauthentication or auth.json import replaces that account's credentials
- **THEN** the stored warm-up preference remains unchanged

#### Scenario: Global disable still prevents warm-up traffic

- **GIVEN** global limit warm-up is disabled
- **WHEN** OAuth or auth.json import creates an enrolled account
- **THEN** the global switch remains disabled
- **AND** background usage refresh does not send warm-up traffic for that account
