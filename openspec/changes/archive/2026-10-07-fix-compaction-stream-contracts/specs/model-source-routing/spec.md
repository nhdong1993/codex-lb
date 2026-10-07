## ADDED Requirements

### Requirement: Standalone source compaction preserves stream contracts

Both standalone compact routes MUST require streaming capability during initial
source selection and disabled-source probing, including raw-model alias and
normalized-model fallback. Existing retained-state ownership checks MUST still
apply before dispatch or reservation.
If no streaming candidate is available but an enabled or disabled non-streaming
source claims the model under the same selection policy, compact MUST return
the existing source-unavailable or disabled error before subscription dispatch
or reservation. Recorded subscription continuity and file pins MUST retain
their existing precedence.

The compact collector MUST preserve valid source Responses usage observed at
the event root or inside a response event when terminal response usage is absent
or null. The compact JSON, request log and quota settlement MUST use the same
validated input/output/cached/reasoning counters. Terminal response usage, when
present, MUST retain precedence and validation; collection MUST remain bounded
and support events up to the existing compact event size limit.

Schema validation failures while translating upstream terminal errors MUST
produce HTTP 502 with the existing `invalid_upstream_response` error code and an
error request log. Existing generic upstream error translations MUST remain
errors. These failures
MUST release the reservation and admission, MUST NOT be recorded as client
cancellation and MUST NOT retry through another source after opening the stream.

#### Scenario: Streaming model fallback remains available for compact

- **GIVEN** a raw model alias has only a non-streaming source and its normalized model has a permitted streaming source
- **WHEN** either standalone compact endpoint receives a portable request
- **THEN** it selects the same streaming model/source as the equivalent HTTP terminal-trigger request
- **AND** it does not return a spurious source-busy error

#### Scenario: Disabled streaming fallback is recognized

- **GIVEN** the raw alias has a non-streaming source and the normalized streaming model is disabled
- **WHEN** either standalone compact endpoint receives a portable request
- **THEN** the existing disabled-source denial applies before dispatch or reservation

#### Scenario: Usage outside the terminal response is retained

- **GIVEN** a source supplies valid Responses usage at an SSE event root or in an earlier response event
- **AND** the terminal response omits usage or reports null usage
- **WHEN** either standalone compact endpoint completes on a limited API key
- **THEN** it returns successful compact JSON including the observed usage
- **AND** its usage reservation finalizes with the observed counters exactly once

#### Scenario: Terminal usage retains precedence

- **GIVEN** earlier SSE usage differs from terminal response usage
- **WHEN** the compact collector completes
- **THEN** terminal response usage drives both compact JSON and settlement
- **AND** malformed terminal usage does not silently reuse earlier usage

#### Scenario: Malformed upstream errors remain upstream failures

- **WHEN** a source terminal error contains fields invalid for the error schema, such as numeric `code`
- **THEN** either compact endpoint returns HTTP 502 `invalid_upstream_response`
- **AND** the log records an upstream error, the reservation/admission are released and only one source attempt occurs
