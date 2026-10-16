## Why

On 2026-10-16, Codex clients lost MCP tools, sub-agent tools and web search on the `http/*` source models. Codex 0.162 sends MCP and multi-agent tools as `namespace` declarations, `apply_patch` as a freeform `custom` tool, and `web_search` as a hosted tool. codex-lb forwards only `function` tools to a model source unless that source model declares the other types in `raw_metadata_json`. Those models declared nothing, and the proxy dropped the tools without a trace. Fixing the problem required hand-editing JSON in the database.

The dashboard has no control for these declarations. The existing **Tools** checkbox only advertises parallel tool calls in the catalog, which suggests the opposite of what the proxy does. The model list is also a single comma-separated text line (`alias=upstream, …`), which is hard to read and edit once a source carries many models. It cannot disable one model either.

## What Changes

- Replace the one-line model input on the create/edit source dialogs with a row editor: one row per model, holding the public model ID, an optional upstream target and an enabled switch. It includes add/remove row actions, a filter for long lists and a bulk-paste box that accepts the existing `alias=upstream` comma/newline syntax.
- Keep each row's identity while editing, so renaming a row's public ID or adding an upstream target preserves that model's capabilities, pricing and raw metadata.
- Add a **Tool calling** section to the source form. It holds the existing tool-support advertisement switch and per-type forwarding toggles for *MCP & sub-agents* (`namespace`), *apply_patch* (freeform `custom`) and *Web search* (`web_search`). Function tools are shown as always forwarded.
- The toggles write only the metadata keys the proxy already reads: `experimental_supported_tools` entries and `apply_patch_tool_type`. They never write `supports_search_tool`, because Codex reads that flag as "enable tool_search", which defers MCP tools behind a tool type the proxy drops. Types granted by advanced metadata (`multi_agent_version`, `tool_mode: code_mode_only`, `supports_search_tool`) are shown as enabled and cannot be removed from the form.
- Log the source, public model and dropped tool types whenever the proxy removes undeclared tool declarations from a source-bound request.

## Capabilities

### Modified Capabilities

- `model-source-routing`: Replace the text-based alias entry requirement with the row editor contract. Add the dashboard tool-type declaration requirement and the dropped-tool observability requirement.

## Impact

- Frontend: `features/model-sources` form model, create/edit dialogs, form fields, a new row editor component, en/ko/zh-CN strings and tests.
- Backend: one structured log line in the source tool filter (`app/modules/proxy/api.py`), plus a unit test. Routing, the filtering rules and the API contract stay unchanged.
- No migration, no new `CODEX_LB_*` setting and no new dashboard navigation item. The management API already accepts per-model `isEnabled` and `rawMetadataJson`.

## Non-goals

- Per-API-key tool restrictions.
- Changing what `supports_search_tool` means to the proxy, or migrating existing metadata.
- A per-model editor for capabilities and pricing. Those settings still apply source-wide, as they do today.
