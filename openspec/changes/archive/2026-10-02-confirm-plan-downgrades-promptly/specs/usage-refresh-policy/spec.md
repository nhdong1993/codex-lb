## ADDED Requirements

### Requirement: Suspicious paid plans receive bounded priority verification

When background usage refresh is enabled, the system MUST request a priority usage check for an eligible account after a model-entitlement rejection or its first confirmable Free observation. These checks MUST run independently of the fleet scan, coalesce across replicas, use at most three concurrent workers, and allow at most three attempts in a two-minute request window. A first Free observation MUST schedule the follow-up after 15 seconds. Failed or unconfirmed checks MUST retry with a delay and MUST NOT loop indefinitely. Shutdown MUST cancel and await owned work. All existing two-observation, workspace-identity and credential-replacement guards MUST continue to apply. A successful plan change MUST invalidate routing selection caches. Plan verification MUST NOT itself rotate tokens or assign reauthentication solely because the plan changed; actual authentication failures MUST retain the existing guarded refresh and permanent-error handling.

#### Scenario: Free is promptly confirmed without scanning the fleet
- **WHEN** the first eligible usage sample reports Free while thousands of accounts await ordinary refresh
- **THEN** a priority follow-up becomes due after 15 seconds
- **AND** a second agreeing sample persists Free without altering credential bytes

#### Scenario: A paid sample contradicts the suspicion
- **WHEN** priority verification returns a recognized paid plan
- **THEN** pending downgrade evidence is cleared and priority verification completes

#### Scenario: Partial failure and replica contention
- **WHEN** multiple replicas request verification and one upstream endpoint fails
- **THEN** duplicate requests share one attempt budget, each claim has one winner, and the other endpoint is still checked
- **AND** failures preserve existing account health unless explicit authentication evidence requires a change

#### Scenario: Reauthentication supersedes pending work
- **WHEN** new credentials replace an account while old verification is pending or in flight
- **THEN** old work and evidence cannot downgrade or suppress the repaired account
