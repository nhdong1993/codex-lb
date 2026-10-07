## MODIFIED Requirements

### Requirement: Compact source forwarding uses the Responses trigger contract

For a source-owned compact operation, the proxy MUST forward an HTTP Responses
request with `stream: true`, preserve the public model identity at the client
boundary, and send exactly one terminal `compaction_trigger` as the final input
item. It MUST use the source upstream model mapping only on the source wire.

The proxy MUST adapt a successful source stream containing an encrypted
`compaction` or `compaction_summary` output item to the established
`response.compaction` JSON result for standalone compact endpoints. It MUST
preserve a valid upstream compaction item ID, encrypted content, status and
reported input/output/cached/reasoning usage. It MUST return an existing OpenAI error
envelope for source failures and MUST NOT fabricate plaintext summaries.

Source compact attempts MUST settle or release API-key usage
exactly once, publish ownership before returning state-bearing output, and
close the source transport on error, cancellation and timeout. Request logs
MUST identify `request_kind=compaction`, the actual source and source revision
for source attempts.

An upstream transport failure after a source compact stream has opened MUST
return HTTP 502 with an OpenAI upstream-error envelope. The attempt MUST be
logged as an error, MUST release its reservation and admission exactly once,
and MUST NOT replay through a different source credential.

#### Scenario: Encrypted source compaction is returned unchanged

- **WHEN** the source Responses stream completes with an encrypted compaction
  output item and usage
- **THEN** `/responses/compact` returns one normalized `type=compaction` item
- **AND** its encrypted content, valid `cmp_` ID and usage are preserved

#### Scenario: Trigger validation remains fail-fast

- **WHEN** a native Codex request contains duplicate or non-terminal trigger items
- **THEN** it returns the existing invalid-client-payload response
- **AND** no source, subscription account or reservation is used

#### Scenario: Source failure cleans up once

- **WHEN** source compaction fails, is cancelled or times out before a usable
  terminal response
- **THEN** the source transport and admission are closed
- **AND** the reservation is released or settled exactly once
- **AND** the request log records the source attempt as an error or cancellation, as appropriate

#### Scenario: Source compact stream connection breaks

- **GIVEN** the source has opened a compact stream and sent `response.created`
- **WHEN** its connection breaks before a usable compact completion
- **THEN** either standalone compact endpoint returns HTTP 502
- **AND** the source attempt is recorded as an error rather than a client cancellation
- **AND** no other source receives the request and no reservation or admission remains held
