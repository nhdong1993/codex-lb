## ADDED Requirements

### Requirement: Credential replacement generation migrates without identity changes

Accounts SHALL have a non-null integer credential generation initialized to zero for existing and new rows. Import or reauthentication replacing an existing account's credentials MUST atomically advance its generation with replacement and evidence invalidation, even when token values are unchanged. Routine OAuth rotation MUST preserve the generation. Migration MUST preserve historical token, plan and status values and support downgrade/re-upgrade through a single Alembic head.

#### Scenario: Upgrade historical account credentials
- **WHEN** a database containing existing account credentials upgrades
- **THEN** every existing account has credential generation zero and unchanged tokens, plan and status

#### Scenario: Replacement and rotation have distinct generations
- **WHEN** an account rotates tokens routinely and is later reauthenticated
- **THEN** rotation preserves the generation and reauthentication advances it atomically
