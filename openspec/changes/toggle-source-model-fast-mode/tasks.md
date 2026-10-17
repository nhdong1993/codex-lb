## 1. Specification

- [x] 1.1 Write proposal, context and the `model-source-routing` delta; run `openspec validate toggle-source-model-fast-mode --strict`.

## 2. Dashboard

- [x] 2.1 Add Fast detection and the `mergeFastModeMetadata` helper; add `fastMode` to the row state, schema and `modelRowsFromSource`.
- [x] 2.2 Add the per-row Fast switch to the model rows editor; let the rows table scroll sideways on narrow screens so the ID inputs stay usable.
- [x] 2.3 Apply the switch in the create and edit dialogs; include it in the row signature so a switch-only change sends models.
- [x] 2.4 Add en/ko/zh-CN strings; keep locale key parity.

## 3. Tests

- [x] 3.1 Helper tests: add and remove both keys, keep other tiers and keys, no-op when unchanged, new rows off.
- [x] 3.2 Edit dialog tests: switch reflects stored metadata, turn on for one model only, turn off keeps `flex`.
- [x] 3.3 Integration tests: declared tiers reach `/backend-api/codex/models`, `/api/key-dashboard/models` and `/v1/models`; undeclared models advertise none; `service_tier: "priority"` reaches the source on all four Responses paths.
- [x] 3.4 Run targeted pytest, vitest, `tsc -b`, eslint, ruff and the dashboard browser smoke suite serially; capture before/after editor screenshots (desktop and 390px).
