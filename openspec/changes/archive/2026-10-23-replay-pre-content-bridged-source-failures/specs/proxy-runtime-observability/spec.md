## ADDED Requirements

### Requirement: Bridged source failures record a payload-free stream trace

A non-success request log of an attempt of a WebSocket turn bridged to an HTTP/SSE source MUST store in `failure_detail` the trace `source_bridge events=<kinds> handed_off=<stage> replay=<eligible|none>`. `<kinds>` MUST list, in order, the kinds of the first eight observed `error` and `response.*` events with consecutive repeats collapsed, drawn only from `created`, `in_progress`, `queued`, `metadata`, `output_item`, `delta`, `completed`, `incomplete`, `failed`, `error` and `other`, followed by `+` when further kinds were observed, or `none` when no event arrived. `<stage>` MUST be `none`, `prefix` or `content`, the furthest class of event handed to the client transport, where `prefix` is the lifecycle prefix defined by "Bridged turns replay one pre-content source failure" and `content` is any other event, terminals included. `replay=eligible` MUST mark an attempt that qualified for the bridged pre-content replay. Identifiers, metadata values, output text, tool arguments and source error messages MUST NOT be stored. A `success` row MUST NOT carry the trace. Each started replay MUST emit a structured log line naming the failed attempt's request id and the failure code.

#### Scenario: A pre-content reset is traced
- **WHEN** a bridged attempt observes `response.created`, `response.in_progress` and `response.metadata` and then the source resets
- **THEN** its row stores `failure_detail = source_bridge events=created,in_progress,metadata handed_off=none replay=eligible`

#### Scenario: A failure after content is traced
- **WHEN** a bridged attempt relays `response.created`, an output item and three deltas and then the source resets
- **THEN** its row stores `failure_detail = source_bridge events=created,output_item,delta handed_off=content replay=none`

#### Scenario: The trace never stores payload values
- **WHEN** a traced event carries text, ids or a source error message such as `https://private.example`
- **THEN** no request-log field contains those values
