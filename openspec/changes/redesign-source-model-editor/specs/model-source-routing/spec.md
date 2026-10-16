## MODIFIED Requirements

### Requirement: Dashboard model entry supports aliases

The create and edit source forms SHALL present a source's models as editable rows. Each row holds a public model ID, an optional upstream target and an enabled switch. Operators SHALL be able to add rows, remove rows, filter long lists, and bulk-paste entries in the `model` or `alias=upstream-id` syntax separated by commas or newlines. Forms MUST reject a blank public ID, an ID or target longer than 255 characters, a bulk entry with more than one `=` separator or an empty side, and duplicate public IDs. A blank upstream target MUST save identity mapping.

Editing a row MUST preserve the capabilities, pricing and raw metadata of the model the row was loaded from, including when the public ID is renamed. A bulk-pasted `alias=target` entry whose target names an existing model MUST inherit that model's settings. Unrelated edits MUST preserve existing mappings and enablement. Removing a target MUST restore identity behavior. Toggling a row's enabled switch MUST persist that model's `isEnabled` value and MUST NOT change the other models. A row added in the edit form that matches no existing model MUST receive the form's current source-wide settings: capabilities, limits, pricing, reasoning and tool declarations.

#### Scenario: Rename an existing model for clients

- **WHEN** an operator gives the existing `cd/linxaq` row the public ID `cd/gpt-6-astra` and the upstream target `cd/linxaq`
- **THEN** the saved public model is `cd/gpt-6-astra` with target `cd/linxaq`
- **AND** its existing multi-agent metadata and model settings are retained

#### Scenario: Bulk paste adds rows

- **WHEN** an operator pastes `http/a=a, http/b=b` into the bulk box of a source that already lists `http/a`
- **THEN** one new row `http/b` with target `b` is added
- **AND** the existing `http/a` row is unchanged

#### Scenario: Duplicate public IDs are rejected

- **WHEN** two rows hold the same public model ID
- **THEN** the form does not submit and reports the duplicate

#### Scenario: Disable a single model

- **WHEN** an operator turns off the enabled switch of one row and saves
- **THEN** the update sends that model with `isEnabled` false
- **AND** every other model keeps its previous enablement

## ADDED Requirements

### Requirement: Dashboard declares forwarded source tool types

The create and edit source forms SHALL provide a Tool calling section. It holds the existing tool-support switch and a forwarding toggle for each non-function tool type the proxy can forward: MCP and sub-agent tools (`namespace`), `apply_patch` (`custom`) and web search (`web_search`). Function tools MUST be shown as always forwarded.

A toggle MUST be shown on only when every model of the source forwards that type under the proxy's declaration rules. Turning a toggle on MUST add, to every model of the source: `namespace` to `experimental_supported_tools`; `apply_patch_tool_type: "freeform"`; or `web_search` to `experimental_supported_tools`. Turning a toggle off MUST remove those same declarations. On every model, the form MUST also remove `custom` from `experimental_supported_tools` when `apply_patch` is turned off, and `web_search_preview` when web search is turned off. Toggles MUST NOT add or remove `supports_search_tool`, `multi_agent_version` or `tool_mode`.

When every model grants a type through `multi_agent_version`, `tool_mode: "code_mode_only"` or `supports_search_tool`, the toggle MUST be shown on and disabled. The form MUST NOT change tool declarations or any unrelated metadata key on a save in which no tool toggle changed. Turning a toggle on MUST also turn the tool-support switch on.

#### Scenario: Enable MCP forwarding for a source

- **GIVEN** a source whose models declare no tool types
- **WHEN** an operator turns on the MCP & sub-agents toggle and saves
- **THEN** every model's raw metadata lists `namespace` in `experimental_supported_tools`
- **AND** their reasoning and upstream-mapping metadata are unchanged
- **AND** a later Codex request that declares an MCP `namespace` tool reaches the source with that tool

#### Scenario: Advanced metadata locks a type on

- **GIVEN** every model of a source declares `multi_agent_version`
- **WHEN** the operator opens the edit dialog
- **THEN** the MCP & sub-agents toggle is shown on and cannot be turned off

#### Scenario: Search-tool flag is never written

- **WHEN** an operator turns web search on or off and saves
- **THEN** no model's `supports_search_tool` value is added, changed or removed

### Requirement: Source tool filtering is observable

When the proxy resolves source candidates for a Responses HTTP request or WebSocket turn, it SHALL emit one structured log record for each candidate source whose model does not declare some of the request's tool types. The record names the source ID, the public model and the sorted dropped tool types. It MUST NOT include tool definitions, arguments or request content. The proxy MUST NOT emit additional records for the same candidate when it re-shapes the payload for dispatch. A candidate that forwards every declared tool MUST NOT emit the record.

#### Scenario: Undeclared namespace tool is dropped

- **GIVEN** a source model without a `namespace` declaration
- **WHEN** a request declaring a `namespace` tool and a `function` tool is forwarded to it
- **THEN** the source receives only the function tool
- **AND** one log record names the source, the model and the dropped type `namespace`
