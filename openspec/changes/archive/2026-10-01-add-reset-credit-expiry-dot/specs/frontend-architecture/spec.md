## ADDED Requirements

### Requirement: List marks reset credits expiring within three days

Accounts List SHALL show a red circular indicator above the Reset count label when the available count is positive and the nearest reset-credit expiry is in the future with at most 72 hours remaining. The indicator SHALL have a localized accessible description and follow reset-count visibility. It SHALL update within one minute while the page remains open without additional credit requests or changing row actions or height.

#### Scenario: Inclusive three-day threshold
- **WHEN** an account has available reset credits expiring in exactly 72 hours or less but still in the future
- **THEN** its Reset count label has a red dot above it
- **AND** activating that area still opens account details without redeeming a credit

#### Scenario: No expiring credit
- **WHEN** the count is zero or unknown, the expiry is unknown or invalid, the credit has expired, or more than 72 hours remain
- **THEN** no expiry dot is displayed

#### Scenario: Time and visibility changes
- **WHEN** an open List crosses the 72-hour threshold or the expiry instant
- **THEN** the indicator appears or disappears within one minute
- **WHEN** reset-count badges are disabled or the count becomes zero
- **THEN** the indicator is absent
