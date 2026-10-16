## ADDED Requirements

### Requirement: Dashboard surfaces the default source context window

The model source list SHALL show a warning on each source that has at least one enabled model without a stored context window. The warning MUST name every such model and MUST state the default context window, in tokens, that the model catalog advertises for source models without one. A source whose enabled models all declare a context window MUST NOT show the warning. A disabled model without a context window MUST NOT trigger or appear in the warning.

The create and edit source forms SHALL show the same default context window next to the Context Window field while that field is blank, and MUST hide it once the field holds a value.

These warnings MUST NOT block saving and MUST NOT change any stored model value.

#### Scenario: Source model without a context window is named

- **GIVEN** a source with enabled models `http/gpt-6-astra` without a context window and `http/gpt-6-sol` with a context window of 272000
- **WHEN** an operator opens the model source list
- **THEN** that source shows a warning naming `http/gpt-6-astra` and the 128,000-token default
- **AND** the warning does not name `http/gpt-6-sol`

#### Scenario: Fully declared source shows no warning

- **GIVEN** a source whose enabled models all declare a context window
- **WHEN** an operator opens the model source list
- **THEN** that source shows no context-window warning

#### Scenario: Disabled model is ignored

- **GIVEN** a source whose only model without a context window is disabled
- **WHEN** an operator opens the model source list
- **THEN** that source shows no context-window warning

#### Scenario: Blank form field shows the default

- **WHEN** an operator opens the create source form
- **THEN** the Context Window field shows the 128,000-token default
- **AND** typing a value into the field hides it
