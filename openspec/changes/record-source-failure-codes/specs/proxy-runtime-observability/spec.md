## ADDED Requirements

### Requirement: Source failure terminals record the upstream error code

When a source-routed Responses attempt observes a source failure terminal
(`error`, a typeless `error` record or `response.failed`) and its request-log
row is not `success`, the row MUST store the sanitized source error code in
`upstream_error_code`; the first failure terminal carrying a valid code MUST
determine it. A `success` row MUST NOT carry it. Client-visible errors,
`error_code`, `error_message`, status, settlement and account health MUST NOT
change.

#### Scenario: Bridged WebSocket turn records the source error code

- **GIVEN** a streaming Responses source without native WebSocket support
- **WHEN** a WebSocket turn served by the HTTP bridge receives the source SSE
  event `{"type":"error","error":{"type":"server_error","code":"upstream_eof","message":"token at https://private.example"}}`
- **THEN** the client receives the existing sanitized 502
  `model_source_response_failed` error
- **AND** the request log stores `error_code = model_source_response_failed`
  and `upstream_error_code = upstream_eof`

#### Scenario: HTTP stream failure terminal records the code

- **WHEN** a source HTTP Responses stream ends with `response.failed` whose
  `response.error.code` is `server_error`
- **THEN** the request log stores `upstream_error_code = server_error`

#### Scenario: The first failure terminal wins

- **WHEN** a source stream sends an `error` event with code `upstream_eof`
  and later sends `response.incomplete`
- **THEN** the error request log stores `upstream_error_code = upstream_eof`

### Requirement: Source failure codes are sanitized identifiers

The source failure code MUST be read from the failure's error object `code`,
falling back to its `type`; an `error` event without an `error` object MUST use
its top-level `code`, falling back to its top-level `error_type`. The value MUST be
trimmed and lowercased and MUST match `^[a-z0-9][a-z0-9_.:-]{0,63}$`; any other
value MUST be recorded as `null`. The source error message MUST NOT be
persisted or logged.

#### Scenario: Unsafe codes are dropped

- **WHEN** a source failure terminal carries the code `bad code with spaces`
  or a code longer than 64 characters
- **THEN** the request log stores `upstream_error_code = null`

#### Scenario: Type is used when the code is absent

- **WHEN** a source failure terminal carries `{"type":"Server_Error"}` with no
  `code`
- **THEN** the request log stores `upstream_error_code = server_error`

#### Scenario: The source message is never stored

- **WHEN** a source failure terminal's message contains `https://private.example`
- **THEN** no request-log field contains `private.example`
