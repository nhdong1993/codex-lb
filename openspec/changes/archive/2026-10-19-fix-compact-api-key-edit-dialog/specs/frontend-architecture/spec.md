## ADDED Requirements

### Requirement: API key edit dialog remains usable in compact viewports

The dashboard API key edit dialog MUST constrain its outer shell to the visible viewport. Its title, Close control, and Save action MUST remain fully visible at 320x568 and 390x844 viewports, and every form field MUST remain reachable through exactly one internal vertical scroll region. The header and footer MUST remain outside that scroll region, and the dialog shell itself MUST NOT scroll. The dialog SHALL retain its stacked compact layout, two-column desktop layout, shared Dialog primitive, field behavior, and dismissal behavior.

#### Scenario: Compact viewport keeps primary controls visible

- **WHEN** an operator opens Edit for an API key on `/apis` at a 320x568 or 390x844 viewport
- **THEN** the dialog title, Close control, and Save action are fully inside the viewport
- **AND** the dialog shell does not extend above or below the viewport

#### Scenario: Compact form fields use one internal scroller

- **WHEN** the edit form fields exceed the height available between the dialog header and footer
- **THEN** all General and Limits fields are reachable through one internal vertical scroll region
- **AND** no other element inside the dialog scrolls vertically

#### Scenario: Desktop layout remains two columns

- **WHEN** an operator opens the edit dialog at a 1440x900 viewport
- **THEN** the dialog stays inside the viewport with its primary controls visible
- **AND** the form uses two columns
