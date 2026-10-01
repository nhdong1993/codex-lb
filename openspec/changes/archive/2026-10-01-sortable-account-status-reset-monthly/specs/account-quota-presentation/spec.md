## ADDED Requirements

### Requirement: Account lists sort monthly remaining quota

Accounts SHALL offer ascending and descending Monthly quota sorting by raw monthly remaining percentage, independently of the 5h/weekly display preference. Unknown monthly values SHALL sort last in both directions. Monthly-only accounts SHALL retain a single Monthly bar and SHALL NOT substitute their monthly value into 5h or 7d sorting.

#### Scenario: Sort Free accounts by monthly quota
- **WHEN** the operator filters Plan to Free and sorts Monthly ascending
- **THEN** accounts with 0%, 25% and 90% monthly remaining appear in that order, followed by unknown values
- **AND** descending produces 90%, 25%, 0%, then unknown values

#### Scenario: Mixed plans and quota preferences
- **WHEN** a mixed paid/Free list is sorted by Monthly with the display preference set to 5h or weekly
- **THEN** available monthly percentages determine order and accounts without monthly data remain last
- **AND** monthly-only accounts display their Monthly quota bar
