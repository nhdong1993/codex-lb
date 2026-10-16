## 1. Specification

- [x] 1.1 Write proposal, context and the `model-source-routing` delta; run `openspec validate block-subagents-per-model --strict`.

## 2. Backend

- [x] 2.1 Add `source_model_blocks_subagents` and strip `block_subagents` from client-visible catalog metadata.
- [x] 2.2 Add a spawned-sub-agent detector (headers and `client_metadata`, `collab_spawn` / `thread_spawn` only).
- [x] 2.3 Remove `multi_agent_v1` / `collaboration` namespaces (and dependent `tool_choice`) when shaping payloads for blocking models.
- [x] 2.4 Exclude blocking candidates for spawned requests during source candidate resolution; raise `403 subagents_disabled` when none remain, before reservation, on HTTP and WebSocket.

## 3. Frontend

- [x] 3.1 Add the per-row Sub-agents switch to the model rows editor, row state and metadata merge (create and edit).
- [x] 3.2 Add en/ko/zh-CN strings.

## 4. Tests

- [x] 4.1 Route tests on HTTP: namespace removal keeps MCP; spawned request gets 403 with no dispatch and no reservation; header-only and turn-metadata detection; unflagged model and other `x-openai-subagent` values unaffected; pool fallback.
- [x] 4.2 WebSocket route test: spawned turn on a blocking model returns `subagents_disabled` and no frame reaches the source.
- [x] 4.3 Catalog test: flag hidden.
- [x] 4.4 Dashboard tests: switch round-trip, metadata preserved, switch-only change sends models.
- [x] 4.5 Run targeted pytest, vitest, tsc, eslint, ruff, then capture an updated editor screenshot.
