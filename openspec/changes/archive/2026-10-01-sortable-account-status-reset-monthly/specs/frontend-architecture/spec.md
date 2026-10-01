## MODIFIED Requirements

### Requirement: Accounts List headers control sorting

Desktop List SHALL offer keyboard-operable Plan, Status, Reset credits, Subscription, Quota 5h, Quota 7d and Monthly quota header controls. Selecting an inactive header SHALL sort ascending; selecting it again SHALL toggle direction. Active controls SHALL expose visible direction arrows and an accessible direction description. The same ascending/descending modes SHALL be available from the existing sort dropdown at all viewport sizes. Header sorting SHALL preserve the compact row layout.

#### Scenario: Toggle header direction
- **WHEN** an operator activates a List sort header by pointer or keyboard
- **THEN** its ascending order appears with a visible and accessible direction
- **AND** activating it again reverses that order and updates the sort dropdown

#### Scenario: Mobile sorting
- **WHEN** desktop headers are hidden at narrow widths
- **THEN** the operator can select every new sort mode from the sort dropdown

### Requirement: AccountListItem displays a reset-credits count badge

The compact `AccountListItem` SHALL render a count badge pinned to the right-upper radius of the item whenever the account reports `available_reset_credits > 0` and dashboard setting `show_reset_credit_badges` is enabled. The badge SHALL display the integer count, capped visually at `"99+"` when the count exceeds 99. The badge SHALL be absent when `available_reset_credits` is `0` or `show_reset_credit_badges` is disabled. The full-width Accounts List SHALL show a separate Reset column with compact labeled counts, including zero, when show_reset_credit_badges is enabled. Unknown counts SHALL display an unknown marker. Disabling badges SHALL hide the Reset column. The compact selector and Grid header SHALL retain their existing badges. The List badge SHALL use summary data without extra credit requests or a direct redemption action.

#### Scenario: Badge shows the available count
- **WHEN** an `AccountListItem` renders for an account with `available_reset_credits: 3`
- **THEN** a count badge pinned to the item's right-upper radius displays `3`

#### Scenario: Badge caps at 99+
- **WHEN** an `AccountListItem` renders for an account with `available_reset_credits: 120`
- **THEN** the count badge displays `99+`

#### Scenario: Badge absent when zero
- **WHEN** an `AccountListItem` renders for an account with `available_reset_credits: 0`
- **THEN** no count badge is rendered

#### Scenario: Badge visibility follows settings
- **GIVEN** `show_reset_credit_badges` is disabled
- **AND** an account reports `available_reset_credits: 3`
- **WHEN** an `AccountListItem` renders
- **THEN** the reset-credit count badge is absent

#### Scenario: List shows available reset count
- **WHEN** an Accounts List row has three available reset credits and badges are enabled
- **THEN** a compact Reset (3) indicator appears in a separate Reset column
- **AND** zero credits display Reset (0), unknown credits display an unknown marker, and disabling badges hides the column
- **AND** selecting the row opens details without redeeming credits

## ADDED Requirements

### Requirement: List separates account status and reset-credit counts

List SHALL display Plan, Status and available Reset credits in separate desktop columns. Reset counts SHALL display zero distinctly from unknown data. Disabling reset-credit badges SHALL hide the Reset column. Sorting SHALL preserve filters and selection, apply before pagination and return to page one.

#### Scenario: Distinct count values
- **WHEN** accounts report 3, 0 and unknown reset credits
- **THEN** their Reset cells show 3, 0 and an unknown marker respectively
- **AND** status remains in its own column with its existing reason tooltip

#### Scenario: Sort status and counts
- **WHEN** the operator selects ascending Status order
- **THEN** accounts appear in active, paused, rate-limited, quota-exceeded, reauthentication-required and deactivated order
- **AND** descending Status reverses that order
- **WHEN** the operator sorts Reset ascending or descending
- **THEN** counts are ordered numerically in that direction with unknown counts last and equal counts ordered by nearest known expiry first

#### Scenario: Hide reset counts
- **WHEN** reset-credit badge visibility is disabled
- **THEN** List omits both the Reset header and its cells while keeping the other columns aligned
