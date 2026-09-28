## ADDED Requirements

### Requirement: Account list exposes plan and quick Burn First controls

The Accounts Detail, List and Grid views SHALL expose a local plan filter alongside the existing search/status controls. The List view SHALL provide an accessible per-row Burn First toggle that updates the existing account routing policy, reflects the saved state, and does not open the row detail when toggled. Enabling the toggle SHALL set `burn_first`; disabling it SHALL set `normal`. The toggle SHALL be disabled for read-only viewers, pending routing updates, and deactivated or reauthentication-required accounts. Plan badges in account views SHALL use the dashboard request-log visual system and SHALL provide dedicated styles for `prolite` and `promax`.

#### Scenario: Filter by plan
- **WHEN** an operator selects Prolite in the plan filter
- **THEN** only accounts whose stored plan type is `prolite` remain visible in every account view

#### Scenario: Toggle Burn First in a row
- **WHEN** an operator toggles Burn First on a List row
- **THEN** the account routing policy mutation receives `burn_first`, the row remains selected in place, and the detail dialog does not open

#### Scenario: Plan badge styles
- **WHEN** account or request-log data has plan type Prolite or Promax
- **THEN** its badge uses the shared plan style map and remains readable in light and dark themes
