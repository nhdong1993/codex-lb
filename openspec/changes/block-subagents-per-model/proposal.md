## Why

Operators want to stop Codex sub-agents (`spawn_agent`) on specific models without losing MCP tools. Today the only lever is the source tool-type filter. Sub-agent tools and MCP tools are both `namespace` declarations, so the filter can block sub-agents only by dropping every namespace, MCP included. For code-mode models it cannot block them reliably at all, because Codex may expose `spawn_agent` inside the `exec` tool, which runs on the client.

A Codex 0.162.1 capture on 2026-10-16 showed two signals codex-lb can act on:

- Sub-agent tools are declared as namespaces named `multi_agent_v1` (regular models) or `collaboration` (code mode with `multi_agent_version: "v2"`). MCP namespaces are named `mcp__<server>`.
- Every request made by a spawned sub-agent thread carries `x-openai-subagent: collab_spawn` and a turn metadata `subagent_kind: "thread_spawn"`. These appear both as headers and inside the body's `client_metadata`, including on WebSocket `response.create` frames. Requests from the parent thread carry neither.

## What Changes

- Add a per-model `block_subagents` flag to source model metadata.
- When the flag is set, the proxy removes the `multi_agent_v1` and `collaboration` namespace declarations from Responses requests routed to that model and keeps every other tool, including MCP.
- When the flag is set, the proxy refuses spawned sub-agent requests for that model on HTTP and WebSocket. It returns `403 subagents_disabled` before quota reservation or upstream dispatch. In a source pool, it routes the request to a candidate that allows sub-agents when one exists.
- Hide the flag from client-visible catalogs.
- Add a per-row **Sub-agents** switch to the dashboard model editor.

## Capabilities

### Modified Capabilities

- `model-source-routing`: add the per-model sub-agent blocking requirement and the dashboard switch requirement.

## Impact

- Backend: model-source catalog helpers, source candidate resolution and payload shaping in `app/modules/proxy/api.py`, plus a small sub-agent detection helper.
- Frontend: model rows editor, form logic, edit/create dialogs, en/ko/zh-CN strings and tests.
- No migration, no new setting and no API contract change; the flag lives in `raw_metadata_json`.
- Builds on `redesign-source-model-editor`, which introduces the row editor.

## Non-goals

- Per-API-key sub-agent blocking.
- Models served through subscription accounts, which have no per-model metadata.
- Other auxiliary Codex threads such as review, compaction or memory, which use other `x-openai-subagent` values.
