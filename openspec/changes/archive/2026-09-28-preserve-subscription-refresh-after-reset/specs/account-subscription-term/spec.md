# Spec Delta

## ADDED Requirements

### Requirement: Reset reconciliation preserves a newer compatible subscription term

When a reset-quota reconciliation result updates an account, the account list and dashboard MUST retain a subscription term from a successful refresh when that term belongs to the same account identity, plan, ChatGPT account and workspace, is not from an older credential refresh, and has a newer successful check timestamp than the reset result. The reconciliation state used by account and dashboard polls MUST retain the same merged subscription so an older in-flight response cannot restore the previous term. Quota, usage, status and reset-credit fields from the reset result MUST still be applied. Fresh polls started after the merge MUST remain authoritative, including newer inactive results and changed account sources.

#### Scenario: Delayed reset summary follows a successful refresh
- **WHEN** a reset summary containing an older subscription term arrives after a successful refresh containing a newer term for the same account
- **THEN** the account list and dashboard keep the newer term
- **AND** the reset summary's quota fields are applied

#### Scenario: Reconciliation state remains consistent after the merge
- **WHEN** an account or dashboard poll started before a reset or subscription merge completes after that merged result
- **THEN** it keeps the newer compatible subscription term
- **AND** it keeps the reconciled quota fields

#### Scenario: Different account identity is not transplanted
- **WHEN** a reset result belongs to a different plan, ChatGPT account, workspace or account identity, or records a newer credential refresh
- **THEN** the previously cached subscription term is not copied into that reset result

#### Scenario: A later authoritative response clears the term
- **WHEN** a reset summary or fresh poll contains a newer successful inactive subscription check
- **THEN** the account list and dashboard show no active term
- **AND** an earlier paid term is not restored from reconciliation state
