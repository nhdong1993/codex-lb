## MODIFIED Requirements

### Requirement: Client family allowlist mapping

Telemetry client statistics MUST report only canonical client-family identifiers produced by the documented mapping table, MUST map any unmatched user-agent group to `other`, and MUST NOT transmit raw user-agent group values.

The canonical mapping table (raw `useragent_group` → family):

| Raw group(s) | Family |
| --- | --- |
| `codex_exec`, `codex-tui`, `codex_cli_rs` | `codex-cli` |
| `Codex Desktop` | `codex-desktop` |
| `codex_vscode` | `codex-vscode` |
| `AsyncOpenAI` | `openai-sdk-python` |
| `OpenAI` | `openai-sdk-js` |
| `ai`, `ai-sdk` | `vercel-ai-sdk` |
| `opencode` | `opencode` |
| `Mozilla` | `browser` |
| `curl`, `undici`, `node`, `Python-urllib`, `python-requests`, `aiohttp` | `script` |
| anything else | `other` |

The payload MUST include `clients_other_ratio` so mapping coverage decay is observable
without ever transmitting the unmatched raw values.

#### Scenario: Private tool names never leave the instance

- **WHEN** request logs contain a user-agent group not present in the mapping table
- **THEN** its traffic is attributed to `other` and the raw group string is absent from the
  payload

#### Scenario: Codex CLI variants collapse to one family

- **WHEN** traffic exists from `codex_exec`, `codex-tui`, and `codex_cli_rs` (the interactive
  Codex CLI's native user-agent fingerprint)
- **THEN** the payload reports a single `codex-cli` family combining all three
