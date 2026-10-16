## 1. Specification

- [x] 1.1 Write proposal, context and the `model-source-routing` delta; run `openspec validate redesign-source-model-editor --strict`.

## 2. Backend observability

- [x] 2.1 Log the source ID, public model and sorted dropped tool types in the source tool filter; never log tool bodies.
- [x] 2.2 Add route-level tests on `/backend-api/codex/responses`: dropped namespace and web_search tools produce exactly one record, and a source declaring every tool produces none.

## 3. Model row editor

- [x] 3.1 Replace the `models` text field with row state (public ID, upstream target, enabled, origin model). Validate blank, overlength and duplicate IDs.
- [x] 3.2 Build the row editor component: add/remove rows, enabled switch, a filter for long lists, and bulk paste using the existing syntax that skips IDs already present.
- [x] 3.3 Wire create and edit dialogs. The edit dialog matches each row to its origin model (falling back to the pasted-alias target), sends per-model `isEnabled`, and sends `models` only when rows or model settings change.

## 4. Tool calling section

- [x] 4.1 Add pure helpers that derive tool-type state (on, locked) across a source's models and apply toggle changes to raw metadata without touching unrelated keys.
- [x] 4.2 Move the tool-support switch into a Tool calling section with function (always on), MCP & sub-agents, apply_patch and web search toggles. Turning a type on also turns tool support on.
- [x] 4.3 Apply tool declarations only when a toggle changed, on create and edit.

## 5. Strings and tests

- [x] 5.1 Add en/ko/zh-CN strings and remove unused ones; keep locale key parity.
- [x] 5.2 Unit tests for the parsing, validation and metadata helpers; dialog tests for rename preservation, bulk paste, disabling one model, tool toggle round-trips, locked advanced grants and untouched metadata.
- [x] 5.3 Run targeted vitest, `tsc -b`, eslint, ruff and targeted pytest serially, then capture before/after screenshots of the edit dialog.
