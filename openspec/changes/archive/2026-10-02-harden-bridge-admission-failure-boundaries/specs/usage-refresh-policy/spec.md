## ADDED Requirements

### Requirement: Confirmed downgrade evidence survives failed persistence

Confirmed agreeing Free observations MUST remain available until the guarded plan metadata write succeeds. A routine OAuth token rotation that rejects a stale write MUST NOT reset the observation sequence or bypass credential-generation guards. A later check within the original attempt budget MUST be able to persist the confirmed downgrade using current credentials. Successful persistence MUST clear consumed evidence, and credential replacement MUST continue to discard old evidence.

Evidence clearing by ordinary as well as priority refreshes MUST be fenced against credential replacement. The credential condition MUST be evaluated after serializing with replacement, so an older successful refresh cannot delete the replacement's new observations.

Routine token rotation MUST NOT prevent a recognized paid sample from clearing earlier Free evidence or prevent a first Free observation from scheduling priority verification. These mutations MUST use the persisted replacement generation, not token ciphertext, to distinguish rotation from import/reauthentication.

#### Scenario: Routine rotation races the confirming plan write
- **WHEN** a priority worker confirms Free but routine token rotation causes its metadata write to fail
- **THEN** the account remains unchanged and the agreeing observations remain available
- **AND** the next available attempt can persist Free, complete verification and clear the consumed observations without marking the account reauth-required

#### Scenario: Replacement occurs after a rejected confirming write
- **WHEN** credentials are replaced before the remaining priority attempt
- **THEN** replacement clears the old evidence/check and the rejected worker cannot apply or clear the replacement generation's evidence

#### Scenario: Replacement overtakes ordinary evidence consumption
- **WHEN** an ordinary refresh persists Free and credential replacement records new Free evidence before the older refresh consumes its observations
- **THEN** the older clear preserves the replacement's evidence
- **AND** its pending verification can confirm Free using the remaining original attempts

#### Scenario: Paid reset races rotation
- **WHEN** a recognized paid sample clears earlier Free evidence while routine token rotation commits
- **THEN** the paid sample clears the evidence and a later single Free sample cannot confirm a downgrade

#### Scenario: First Free enqueue races rotation
- **WHEN** routine rotation commits after recording the first Free sample but before requesting priority verification
- **THEN** the same credential generation can enqueue or reopen verification within the existing budget
- **AND** a genuine replacement, including one with unchanged token values, still fences the stale enqueue
