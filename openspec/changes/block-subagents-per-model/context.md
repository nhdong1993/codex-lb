# Context: block-subagents-per-model

## How Codex runs a sub-agent (observed with Codex CLI 0.162.1, 2026-10-16)

1. The parent request declares sub-agent tools as a namespace:
   - regular models: `{"type":"namespace","name":"multi_agent_v1","tools":[spawn_agent, wait_agent, send_input, close_agent, resume_agent]}`;
   - code mode with `multi_agent_version: "v2"`: `{"type":"namespace","name":"collaboration","tools":[spawn_agent, followup_task, send_message, wait_agent, list_agents, interrupt_agent]}`;
   - code mode without `multi_agent_version`: no namespace. Instead, `tools.multi_agent_v1__spawn_agent(...)` appears inside the `custom exec` tool description and runs on the client.
2. The model calls `spawn_agent`. The Codex client creates a new thread and returns `{"agent_id","nickname"}`.
3. The new thread sends its own model requests with:
   - headers `x-openai-subagent: collab_spawn` and `x-codex-parent-thread-id`;
   - the same values inside the body's `client_metadata`;
   - `x-codex-turn-metadata` with `"thread_source":"subagent"`, `"subagent_kind":"thread_spawn"` and `parent_thread_id`.

   It shares `session-id` with the parent.

## Decisions

- **Two layers.** Removing the namespace declarations stops the model from calling `spawn_agent`, so turns are not wasted. Refusing spawned requests is the hard block, and it is the only layer that works when `spawn_agent` lives inside `exec`.
- **Match by namespace name, not type.** MCP namespaces (`mcp__*`) must survive. The type-level filter in `source_model_supported_tool_types` is unchanged and still applies first.
- **Match only `collab_spawn` / `thread_spawn`.** The Codex binary also has guardian review, compaction and memory threads that may use `x-openai-subagent` with other values. Blocking those would break unrelated features.
- **Policy lives on the model the sub-agent uses.** `spawn_agent` accepts a model override, so a sub-agent can run on another model. That model's own flag decides.
- **Pools.** A model can be served by several sources with different flags. Spawned requests skip the blocking candidates and fail only when no candidate is left.
- **Metadata key, no migration.** This follows `upstream_model` and `source_request_overrides`. Like `source_request_overrides`, the key is stripped from client-visible catalogs.

## Limitations

- Subscription-account models have no per-model metadata and are not covered.
- Detection relies on client-supplied signals. Official Codex clients send them; custom clients might not. The declaration-removal layer still applies to those clients.
- A rejected sub-agent request produces no request-log row, because nothing is dispatched. It is visible as the `subagent_request_blocked` log line.

## Example

```json
{"upstream_model": "gpt-6-astra", "experimental_supported_tools": ["namespace", "custom", "web_search"], "block_subagents": true}
```

With this metadata, MCP, apply_patch and web search are forwarded, `multi_agent_v1` is removed, and spawned sub-agent requests for this model receive `403 subagents_disabled`.
