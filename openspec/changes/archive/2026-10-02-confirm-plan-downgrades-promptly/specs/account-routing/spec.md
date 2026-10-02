## ADDED Requirements

### Requirement: Model rejection temporarily excludes the rejected account and model

An exact model-entitlement rejection MUST trigger priority plan verification and temporarily exclude the most recently rejected account/model pair across replicas until the shared two-minute request window expires. Repeated errors MUST NOT extend the window or reset the attempt budget. It MUST NOT penalize global account health, infer Free without usage confirmation, or block unrelated models. Exclusion MUST apply to routing availability while retaining account ownership resolution; a strict file or conversation owner MUST NOT move to another account because of this exclusion. Expired evidence and evidence belonging to replaced credentials MUST NOT suppress routing.

#### Scenario: A repeated request uses another eligible account
- **WHEN** account A rejects model M and a movable request for M arrives during the exclusion window
- **THEN** account A is excluded and another eligible account can serve the request
- **AND** account A remains eligible for unrelated models

#### Scenario: Hard ownership remains authoritative
- **WHEN** the rejected pair belongs to the required file or conversation owner
- **THEN** the request fails according to the existing owner-unavailable contract without crossing accounts

#### Scenario: Expiration restores normal model selection
- **WHEN** the two-minute exclusion window expires
- **THEN** normal catalog, quota and authentication checks determine eligibility again
