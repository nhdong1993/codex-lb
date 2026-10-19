## MODIFIED Requirements

### Requirement: Source-routed requests report upstream-measured generation timings

The proxy MUST record upstream-reported generation timing on the request log
for source-routed chat/responses/audio-transcription requests when the
OpenAI-compatible source's response body includes a `metrics` object with
`time_to_first_token_ms` and `generation_time_ms`. The proxy MUST set
`latency_first_token_ms` to the reported time-to-first-token and `latency_ms`
to the sum of time-to-first-token and generation time, using the same
request-log fields subscription-backed requests already populate. A valid
upstream timing pair MUST be recorded unchanged and MUST NOT be combined with
proxy-measured values. On the chat-completions and audio-transcription routes,
sources that do not return a usable `metrics` object MUST leave both fields
`null`. On source-routed Responses requests, the proxy-measured fallback
requirement applies instead. Negative or non-numeric values MUST be rejected
rather than recorded. Non-finite numeric values (`NaN`, positive infinity, or
negative infinity) MUST also be rejected rather than failing or interrupting
the proxied request.

#### Scenario: Source metrics populate TTFT and total latency

- **GIVEN** an OpenAI-compatible source's chat completion response includes
  `metrics: {time_to_first_token_ms: 108.83, generation_time_ms: 162.98}`
- **WHEN** the request is logged
- **THEN** the request log's `latency_first_token_ms` is `109`
- **AND** the request log's `latency_ms` is `272`

#### Scenario: Streamed responses capture metrics from the final frame

- **GIVEN** a source-routed streaming chat completion whose final SSE frame
  carries both `usage` and `metrics`
- **WHEN** the stream completes successfully
- **THEN** the request log records the same `latency_first_token_ms` /
  `latency_ms` derived from that frame's `metrics`

#### Scenario: Missing metrics leaves latency fields null

- **GIVEN** an OpenAI-compatible source's chat completion response includes no
  `metrics` object
- **WHEN** the request is logged
- **THEN** `latency_ms` and `latency_first_token_ms` remain `null`, unchanged
  from prior behavior

#### Scenario: Dashboard retains generation-only throughput semantics

- **GIVEN** a source response reports `time_to_first_token_ms: 108.83`,
  `generation_time_ms: 162.98`, and `9` output tokens, including zero reasoning
  tokens
- **WHEN** the existing dashboard computes tokens per second as non-reasoning
  output tokens divided by `latency_ms - latency_first_token_ms`
- **THEN** it reports approximately `55.2` generation tokens per second
- **AND** it does not substitute an upstream `tokens_per_second` value that may
  include TTFT

#### Scenario: Non-finite metrics are ignored safely

- **GIVEN** a source response contains `NaN` or infinity in either timing field
- **WHEN** the proxy parses the optional metrics
- **THEN** neither upstream timing value is recorded
- **AND** the otherwise successful proxied request is not interrupted

#### Scenario: Usage-unavailable non-stream error keeps upstream timings

- **GIVEN** a limited API key and a non-stream source Responses body without
  `usage` but with `metrics: {time_to_first_token_ms: 25, generation_time_ms: 120}`
- **WHEN** the proxy answers `usage_unavailable` and logs the error
- **THEN** the request log records `latency_first_token_ms = 25` and
  `latency_ms = 145`


## ADDED Requirements

### Requirement: Source-routed Responses requests fall back to proxy-measured timings

When a source-routed Responses request has no valid upstream timing pair, the
proxy MUST measure both timing fields itself from the moment it sends the
attempt, as non-negative integer milliseconds on the owner clock. A valid
upstream pair MUST take precedence. An attempt never sent MUST leave both
fields `null`. Non-stream and compaction responses MUST record `latency_ms`
only.

#### Scenario: Upstream metrics win

- **GIVEN** a source Responses stream whose terminal carries a valid
  `metrics` pair
- **WHEN** the row is written
- **THEN** both fields come from that pair and no proxy-measured value is mixed in

#### Scenario: Malformed metrics fall back

- **GIVEN** a source Responses stream whose `metrics` contain `NaN`
- **WHEN** the row is written
- **THEN** both fields are the proxy-measured values

#### Scenario: Non-stream records latency only

- **WHEN** a non-stream source Responses request without upstream metrics completes
- **THEN** `latency_ms` is recorded and `latency_first_token_ms` is `null`

#### Scenario: Attempt never sent stays blank

- **WHEN** a dispatch is abandoned before it was sent to the source
- **THEN** both fields are `null`

#### Scenario: WebSocket and bridged turns record timing per turn

- **WHEN** a native source WebSocket turn or a WebSocket turn bridged to an
  HTTP-only source relays a text delta and a terminal
- **THEN** that turn's row records `latency_first_token_ms` no greater than
  `latency_ms`
- **AND** a later turn on the same socket measures from its own send

### Requirement: Proxy-measured source TTFT is stamped at client handoff

The proxy-measured `latency_first_token_ms` MUST use the subscription-path
time-to-first-token classifier and MUST be stamped when the qualifying frame is
handed to the client transport: after continuity publication on HTTP and after
acquiring the downstream send lock on WebSocket. `response.created`,
`response.in_progress`, keepalives and blank reasoning-summary placeholders MUST
NOT start it. A response that hands off no qualifying frame MUST leave it `null`.

#### Scenario: Blank reasoning placeholder does not start TTFT

- **GIVEN** a source stream whose first reasoning-summary delta is a blank
  `<!-- -->` line, followed by a text delta
- **WHEN** the row is written
- **THEN** `latency_first_token_ms` is measured to the text delta

#### Scenario: Frame cancelled before handoff does not count

- **GIVEN** a WebSocket text delta waiting for the downstream send lock
- **WHEN** the send is cancelled before it acquires the lock
- **THEN** no time-to-first-token value is recorded from that frame

### Requirement: Proxy-measured source latency ends at the first relayed terminal

The proxy-measured `latency_ms` MUST end when the first terminal event
(`response.completed`, `response.incomplete`, `response.failed` or `error`) is
handed to the client, or, when none was, when the attempt begins finalizing.
That terminal MUST close the time-to-first-token window, finalizing a pending
reasoning-summary delta at that instant. Later events MUST NOT change either
value.

#### Scenario: HTTP stream excludes a post-terminal tail

- **GIVEN** a source stream that sends `response.created`, then a text delta
  300 ms after the send, then `response.completed` 1000 ms after the send, and
  closes its body 3000 ms after the send
- **WHEN** the request log row is written
- **THEN** `latency_first_token_ms` is `300` and `latency_ms` is `1000`
- **AND** the dashboard TPS is non-reasoning output tokens divided by 0.7 s

#### Scenario: Completed-only answer keeps TTFT blank

- **GIVEN** a source stream whose only content is the `response.completed`
  envelope, followed by a stray text delta
- **WHEN** the row is written
- **THEN** `latency_first_token_ms` is `null`
- **AND** `latency_ms` ends at the relayed terminal
