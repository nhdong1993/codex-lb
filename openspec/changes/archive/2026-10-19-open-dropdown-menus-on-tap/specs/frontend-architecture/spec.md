## ADDED Requirements

### Requirement: Dashboard dropdown menus open on a completed tap

Dashboard dropdown menu triggers MUST NOT open their menu when a touch pointer goes down. A touch interaction MUST toggle the menu only when the tap completes, and a touch that becomes a scroll gesture MUST leave the menu closed while the surrounding content scrolls. Mouse `pointerdown` and keyboard opening (Enter, Space, ArrowDown) SHALL keep their existing behavior, and controlled `open`/`onOpenChange` usage SHALL keep working.

#### Scenario: Touch scroll starting on a trigger does not open the menu

- **WHEN** an operator on a touch screen starts a vertical swipe on a dropdown trigger inside a scrollable dashboard form
- **THEN** the form scrolls
- **AND** the dropdown menu stays closed

#### Scenario: Touch tap opens the menu

- **WHEN** an operator taps a dropdown trigger on a touch screen
- **THEN** the dropdown menu opens

#### Scenario: Mouse and keyboard opening are unchanged

- **WHEN** an operator presses the primary mouse button on a dropdown trigger, or presses Enter, Space or ArrowDown on a focused trigger
- **THEN** the dropdown menu opens as before
