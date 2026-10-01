## MODIFIED Requirements

### Requirement: Accounts List headers control sorting

Desktop List SHALL offer keyboard-operable Plan, Status, Reset credits and Subscription header controls. Quota 5h, Quota 7d and Monthly sorting SHALL be presented in a separate labeled group above the headers. The quota data column SHALL have a shared Quota remaining heading rather than window-specific sort buttons. Selecting an inactive header SHALL sort ascending; selecting it again SHALL toggle direction. Active controls SHALL expose visible direction arrows and an accessible direction description. The same ascending/descending modes SHALL be available from the existing sort dropdown at all viewport sizes. Header sorting SHALL preserve the compact row layout.

#### Scenario: Toggle header direction
- **WHEN** an operator activates a List sort header by pointer or keyboard
- **THEN** its ascending order appears with a visible and accessible direction
- **AND** activating it again reverses that order and updates the sort dropdown

#### Scenario: Mobile sorting
- **WHEN** desktop headers are hidden at narrow widths
- **THEN** the operator can select every new sort mode from the sort dropdown

## ADDED Requirements

### Requirement: List metadata remains readable on narrow screens

At widths down to 320 CSS pixels, List Plan, Status and Reset badges SHALL wrap or stack when necessary without intersecting each other or overflowing the row. Desktop SHALL retain separate aligned metadata columns. These behaviors SHALL hold for all supported interface languages and with reset-credit badges enabled or disabled.

#### Scenario: Long recovery status on a phone
- **WHEN** an Enterprise account with reauthentication-required status and 12 reset credits is shown at 320px
- **THEN** all three badges remain readable and do not overlap
- **AND** the account row remains operable

#### Scenario: Quota controls do not impersonate quota data columns
- **WHEN** a mixed paid/Free List uses both, 5h-only or Weekly quota display
- **THEN** a single Quota remaining heading describes the quota data region
- **AND** the separate labeled quota sort group offers 5h, 7d and Monthly directions
- **AND** Free monthly-only rows retain one Monthly bar
