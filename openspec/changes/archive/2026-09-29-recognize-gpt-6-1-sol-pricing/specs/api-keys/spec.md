## ADDED Requirements

### Requirement: GPT-6.1 Sol request cost pricing is recognized

The system MUST recognize `gpt-6.1-sol`, case-insensitively and with family-specific suffixed aliases, as a separate canonical price entry when computing API-key reservations, settled usage, request-log costs, and aggregate costs. It MUST use these USD-per-1M-token rates in input / cached-input / output order:

| Context | Standard | Fast/priority | Flex |
| --- | --- | --- | --- |
| Up to 272,000 input tokens | `2 / 0.1 / 10` | `4 / 0.2 / 20` | `1 / 0.05 / 5` |
| More than 272,000 input tokens | `4 / 0.2 / 15` | `8 / 0.4 / 30` | `2 / 0.1 / 7.5` |

Total input, including cached input, MUST select the context band for the full request. Cached-input tokens MUST be deducted from uncached input before costing. GPT-6 Sol MUST retain its existing prices, and unrecognized GPT-6.1 families MUST remain unpriced.

#### Scenario: Canonical and suffixed names retain separate model identity

- **WHEN** cost accounting receives `gpt-6.1-sol`, `GPT-6.1-SOL`, or `gpt-6.1-sol-2026-09-29`
- **THEN** it resolves the canonical price entry `gpt-6.1-sol`
- **AND** aggregate costs remain separate from `gpt-6-sol`

#### Scenario: Cached usage receives GPT-6.1 Sol rates in logs and settlement

- **WHEN** a completed GPT-6.1 Sol request has 200,000 input tokens, 100,000 cached input tokens, and 100,000 output tokens
- **THEN** its request-log cost and API-key settled cost are `$1.21` for Standard, `$2.42` for Fast/priority, or `$0.605` for Flex
- **AND** the request-log API returns the corresponding input, cached-input, output, and total cost breakdown

#### Scenario: Priced reservations enforce an exhausted cost limit before upstream dispatch

- **GIVEN** an in-flight GPT-6.1 Sol request reserves the remaining API-key cost budget under the existing bounded reservation policy
- **WHEN** the client submits another request before the first reservation settles
- **THEN** the system rejects the additional request through the existing quota error path before upstream dispatch

#### Scenario: Long-context cost includes cached input

- **WHEN** a GPT-6.1 Sol request has 300,000 input tokens, 50,000 cached input tokens, and 100,000 output tokens
- **THEN** its Standard cost is `$2.51`, Fast/priority cost is `$5.02`, and Flex cost is `$1.255`

#### Scenario: Exact threshold retains short-context rates

- **WHEN** a GPT-6.1 Sol request has exactly 272,000 total input tokens
- **THEN** short-context rates apply for its service tier
- **WHEN** its total input grows to 272,001 tokens
- **THEN** long-context rates apply for its service tier

#### Scenario: Unknown families do not inherit Sol pricing

- **WHEN** cost accounting receives `gpt-6.1`, `gpt-6.1-astra`, or `gpt-6.1-unknown`
- **THEN** it has no resolved pricing entry
