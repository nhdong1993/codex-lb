## ADDED Requirements

### Requirement: Background account-state builds follow the dashboard snapshot

The quota planner tick, the quota planner forecast endpoint and the usage-refresh recovery reconciliation MUST resolve soft drain and the routing tunables from one dashboard-settings snapshot taken per tick or per request outside any runtime lock (the settings cache, or the dashboard-settings row the usage-refresh cycle already read) and MUST pass them into the account-state build. Only a caller without a snapshot (tests, tools) SHALL resolve the environment layer.

#### Scenario: Dashboard turns soft drain off for background builds

- **GIVEN** `CODEX_LB_SOFT_DRAIN_ENABLED` is unset (default on) and the dashboard stores `soft_drain_enabled = false`
- **WHEN** the quota planner tick or forecast endpoint builds its account states, or the usage-refresh recovery evaluates a recoverable account
- **THEN** the states are built with soft drain off and the dashboard's routing tunables
- **AND** the snapshot was taken once for that tick or request, outside any runtime lock

#### Scenario: Caller without a snapshot keeps the environment layer

- **WHEN** `reconcile_recoverable_account_statuses` runs without a dashboard-settings row
- **THEN** soft drain and the routing tunables resolve from the environment layer
