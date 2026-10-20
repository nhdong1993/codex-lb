## 1. Specification

- [x] 1.1 Write the proposal, context and `proxy-runtime-observability` delta. Run `openspec validate record-source-failure-codes --strict`.

## 2. Tests (red first)

- [x] 2.1 Unit: the Responses stream parser records a sanitized failure code. Cover:
  - `error` with an error object;
  - `error` with top-level fields;
  - a typeless error record;
  - `response.failed`;
  - type fallback;
  - lowercasing;
  - unsafe and over-long codes dropped;
  - first failure wins over a later failure and a later `response.incomplete`.
- [x] 2.2 Route (HTTP `/v1/responses`): `response.failed` stores `server_error`; a typeless record stores `overloaded`; `error` then `response.incomplete` stores the first code and never the message.
- [x] 2.3 Route (WebSocket→HTTP bridge): an `error` event stores `upstream_eof`, the client still gets the sanitized 502, and no row field holds the message; `response.failed` stores `server_error`.
- [x] 2.4 Route (native source WebSocket): a failure terminal stores its code.

## 3. Backend

- [x] 3.1 `SourceUsageHolder.terminal_error_code` plus the parser extraction and sanitizer in `forwarding.py`.
- [x] 3.2 `SourceDispatch.write_row()` passes the code as `upstream_error_code` for non-success rows.

## 4. Verify and ship

- [ ] 4.1 Run the targeted suites serially, `ruff check` / `ruff format --check`, and `ty`.
- [x] 4.2 Sync the delta into `openspec/specs/proxy-runtime-observability/spec.md` and `context.md`. Run `openspec validate --specs`.
- [ ] 4.3 Deploy. Confirm that new source failure rows carry `upstream_error_code`.
- [ ] 4.4 Archive after the operator accepts the result.
