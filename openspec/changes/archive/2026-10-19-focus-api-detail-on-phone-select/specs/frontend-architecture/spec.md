## ADDED Requirements

### Requirement: APIs Detail view stays operable when stacked

Below the desktop breakpoint, where the APIs Detail view stacks the key selector above the detail panel, the selector MUST NOT be a separate vertical scroll region, and selecting a key MUST scroll that key's detail panel into view below the sticky header. At the desktop breakpoint the selector SHALL remain a bounded scroll region beside the detail panel, and selecting a key SHALL NOT scroll the page.

#### Scenario: Phone selection reveals the detail panel

- **WHEN** an operator taps a key in the APIs Detail view at a 390x844 viewport
- **THEN** that key's detail panel heading is inside the viewport and not covered by the sticky header

#### Scenario: Phone selector does not trap scrolling

- **WHEN** the APIs Detail view renders at a 390x844 viewport
- **THEN** the key selector does not scroll vertically on its own

#### Scenario: Desktop selection keeps the page in place

- **WHEN** an operator selects a key in the APIs Detail view at a 1440x900 viewport
- **THEN** the selector remains a bounded scroll region
- **AND** the page scroll position does not change
