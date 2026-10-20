## ADDED Requirements

### Requirement: Working-hour updates contain valid clock times

The quota planner settings API MUST reject supplied working-hour times unless
they use ASCII `HH:MM` format with hours from 00 through 23 and minutes from
00 through 59. An invalid update MUST NOT persist any accompanying changes.
Omitted or null times MUST retain their existing values. Reading legacy
settings MUST remain possible, and the existing scheduler fallback for legacy
malformed times MUST remain available.

#### Scenario: Impossible clock time does not change settings

- **WHEN** an operator supplies `99:99`, `24:00`, or `12:60` with another setting
- **THEN** the API returns a validation error and no setting changes

#### Scenario: Boundary clock times are accepted

- **WHEN** an operator supplies `00:00` and `23:59`
- **THEN** both values are saved and returned unchanged

### Requirement: Quota planner timezone settings are validated safely

The quota planner settings API MUST trim and validate every non-empty timezone
update using the supported timezone database before persisting any settings from
the request. Unknown or malformed timezone keys MUST return HTTP 400 with the
dashboard error code `invalid_quota_planner`, leaving the stored settings unchanged.
Omitted, null, or whitespace-only timezone updates MUST retain the stored value.
Forecasting and routing MUST use the existing UTC fallback for already stored
unknown or malformed timezone keys without raising a timezone lookup exception.

#### Scenario: Invalid update leaves settings unchanged

- **GIVEN** the planner has valid saved settings
- **WHEN** a settings update includes `/Europe/Stockholm` or an unknown timezone
- **THEN** the API returns HTTP 400 with code `invalid_quota_planner`
- **AND** none of the settings from the rejected request are persisted

#### Scenario: Valid and omitted timezone updates retain compatibility

- **WHEN** an operator saves ` Europe/Stockholm `
- **THEN** the API stores `Europe/Stockholm`
- **AND** subsequent omitted, null, or blank timezone updates retain that value

#### Scenario: Legacy malformed timezone does not interrupt planning

- **GIVEN** a previously stored timezone contains a malformed key
- **WHEN** forecast or cold-account routing costs are evaluated
- **THEN** the evaluation uses UTC and completes without a timezone lookup exception
- **AND** the stored key remains available for operator correction

