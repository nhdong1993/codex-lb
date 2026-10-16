# Context: redesign-source-model-editor

## Incident (2026-10-16)

Codex Desktop and `codex exec` 0.162 users on the `http/*` models (source "ch-relay (VPS)") lost MCP tools, `spawn_agent` and web search. A local capture of Codex 0.162.1 against the production catalog entry showed this tool list:

```
function exec_command, write_stdin, list_mcp_resources, …, request_user_input, view_image, get_goal, create_goal, update_goal
namespace multi_agent_v1   [spawn_agent, wait_agent, …]
namespace mcp__<server>    [<mcp tools>]
web_search
```

Codex sent these even though the catalog advertised `experimental_supported_tools: []` and `supports_search_tool: false`. The source filter (`_drop_unsupported_source_response_tools`) kept only the `function` tools, because `source_model_supported_tool_types` returned an empty set for models without declarations. Nothing was logged.

## Declaration rules the form mirrors

`source_model_supported_tool_types` grants:

| Type | Granted by |
|---|---|
| `namespace` | `experimental_supported_tools` contains `namespace`, or a nonblank `multi_agent_version` |
| `custom` | `apply_patch_tool_type: "freeform"`, `tool_mode: "code_mode_only"`, or `custom` in `experimental_supported_tools` |
| `web_search` | `web_search` or `web_search_preview` in `experimental_supported_tools`, or `supports_search_tool: true` |

The form owns only the `experimental_supported_tools` entries and `apply_patch_tool_type`. The other keys change what Codex itself does, so the form treats them as advanced metadata: it shows the grant and never edits it.

## Why the form never writes `supports_search_tool`

To Codex, `supports_search_tool: true` means "use tool_search". Codex then stops sending MCP and multi-agent tools as `namespace` declarations and sends a single `tool_search` tool instead. The proxy does not forward `tool_search` to sources, so the tools vanish again. In production on 2026-10-16, setting the flag reproduced the loss. Declaring `web_search` through `experimental_supported_tools` forwards web search without changing Codex's tool layout.

Example metadata that forwards every Codex tool type for a non-code-mode model:

```json
{"apply_patch_tool_type":"freeform","experimental_supported_tools":["namespace","custom","web_search"]}
```

## Row editor decisions

- Rows keep the model name they were loaded from. A rename then carries that model's settings, without the old "alias target equals existing model" heuristic. The heuristic remains for bulk-pasted entries, which have no origin row.
- Capability, pricing and tool settings still apply source-wide, with the change-flag behavior of the edit dialog: a setting is written to every model only when the operator changed it. Per-model divergence stays intact otherwise.
- Bulk paste keeps the old text syntax, so operators can still move whole lists between sources.

## Failure modes

- A toggle shown off while some models forward the type: the form uses "every model" semantics, so turning the toggle on aligns the whole source.
- A type granted only by advanced metadata on some models: turning the toggle off removes the form-owned declarations, but those models keep forwarding the type. This is intentional, because removing the advanced key would change Codex's own behavior.
