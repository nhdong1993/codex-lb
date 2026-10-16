## 1. Specification

- [x] 1.1 Write proposal, context and the `model-source-routing` delta; run `openspec validate warn-default-source-context-window --strict`.

## 2. Dashboard

- [x] 2.1 Add the default context-window constant (mirroring `DEFAULT_SOURCE_CONTEXT_WINDOW`) and a helper that lists enabled models without a context window.
- [x] 2.2 Show the warning on each affected source in the model source list.
- [x] 2.3 Show the default under the Context Window field while it is blank, in the create and edit forms.

## 3. Strings and tests

- [x] 3.1 Add en/ko/zh-CN strings; keep locale key parity.
- [x] 3.2 Tests: helper unit test; list test for a named missing model, a fully declared source and a disabled model; form test for showing and hiding the hint.
- [x] 3.3 Run targeted vitest, `tsc -b` and eslint serially; capture before/after screenshots of the source list.
