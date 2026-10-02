## ADDED Requirements

### Requirement: Priority plan-check migration preserves existing accounts

The additive migration for shared priority plan checks MUST preserve existing account plans, status, credentials and subscription snapshots. Historical accounts MUST have no inferred pending check. The migration MUST maintain one Alembic head and support downgrade and upgrade without altering account data. Pending work MUST cascade on account deletion and be discarded on credential replacement.

#### Scenario: Historical account survives migration round trip
- **WHEN** a database containing a paid account is upgraded, downgraded and upgraded again
- **THEN** its credential bytes, plan and status remain unchanged and the new check table begins empty
