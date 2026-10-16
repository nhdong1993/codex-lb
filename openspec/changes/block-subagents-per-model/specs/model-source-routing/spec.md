## ADDED Requirements

### Requirement: Source models can block Codex sub-agents

A source model MAY declare `"block_subagents": true` in its `raw_metadata_json`. A model without the flag, or with any other value, MUST keep its existing request handling.

For a Responses request routed to a source model that blocks sub-agents, over HTTP or WebSocket and including trailing-slash equivalents, the proxy MUST remove every top-level tool declaration whose `type` is `namespace` and whose `name` is `multi_agent_v1` or `collaboration` before forwarding. It MUST forward every other tool declaration unchanged, including `mcp__*` namespaces. A forced `tool_choice` that names a removed namespace MUST be removed, as MUST matching entries in an `allowed_tools` choice; an `allowed_tools` choice left empty MUST be removed. When no tool remains, the proxy MUST remove `tools`, `tool_choice` and `parallel_tool_calls`.

The proxy MUST treat a request as a spawned sub-agent request when either of these holds: the `x-openai-subagent` header or `client_metadata` field equals `collab_spawn`; or an `x-codex-turn-metadata` header or `client_metadata` field holds a JSON object whose `subagent_kind` equals `thread_spawn`. A spawned sub-agent request MUST NOT be dispatched to a candidate source whose model blocks sub-agents. When candidates that allow sub-agents remain, normal source selection MUST continue among them. When none remain, the proxy MUST reply with status 403 and an OpenAI error envelope of type `invalid_request_error` and code `subagents_disabled`, before quota reservation and upstream dispatch, on both HTTP and WebSocket. Other `x-openai-subagent` values MUST NOT trigger this rule.

The flag MUST NOT appear in client-visible model catalogs.

#### Scenario: Sub-agent tools are removed while MCP is kept

- **GIVEN** a source model that blocks sub-agents
- **WHEN** a request declares a `function` tool, a `multi_agent_v1` namespace, an `mcp__demo` namespace and `tool_choice` naming `multi_agent_v1`
- **THEN** the source receives the function tool and the `mcp__demo` namespace only
- **AND** the forwarded request has no `tool_choice` naming the removed namespace

#### Scenario: Spawned sub-agent request is refused before reservation

- **GIVEN** a source model that blocks sub-agents
- **WHEN** a request carries `client_metadata` with `x-openai-subagent` equal to `collab_spawn`
- **THEN** the proxy replies 403 with code `subagents_disabled`
- **AND** no upstream request is sent and no usage reservation is created

#### Scenario: WebSocket sub-agent turn is refused

- **GIVEN** a WebSocket-capable source model that blocks sub-agents
- **WHEN** a `response.create` frame carries a turn metadata with `subagent_kind` equal to `thread_spawn`
- **THEN** the client receives an error event with code `subagents_disabled`
- **AND** no frame reaches the source

#### Scenario: Other models and other threads are unaffected

- **WHEN** a spawned sub-agent request targets a source model without the flag
- **THEN** it is forwarded as before
- **AND** a request with `x-openai-subagent` equal to `compact` targeting a blocking model is forwarded as before

#### Scenario: Catalog hides the flag

- **WHEN** a client lists models that include a source model with `block_subagents`
- **THEN** the catalog entry contains no `block_subagents` field

### Requirement: Dashboard switches sub-agents per model

The source model editor SHALL show a Sub-agents switch on every model row. The switch MUST be on for models without `block_subagents: true`, and new rows MUST start with it on. Turning a row's switch off and saving MUST store `block_subagents: true` in that model's metadata. Turning it on MUST remove the key. Both changes MUST preserve every other metadata key and every other row. Changing only this switch MUST send a models update.

#### Scenario: Block sub-agents on one model

- **WHEN** an operator turns off Sub-agents on the `http/gpt-6-astra` row and saves
- **THEN** that model's metadata contains `block_subagents: true` alongside its existing keys
- **AND** the other models' metadata is unchanged
