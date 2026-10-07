## Why

Codex compaction requests for a public model owned by an OpenAI-compatible Model
Source are currently forced through subscription-account compaction. The source
alias is then sent to a ChatGPT account, which rejects it even though ordinary
Responses requests for the same model route successfully to the source. The
same bypass affects the standalone Codex compact endpoint.

## What Changes

- Route source-owned Codex terminal `compaction_trigger` requests through the
  existing Responses Model Source selection, alias, ownership and accounting
  policy.
- Implement standalone `/backend-api/codex/responses/compact` and
  `/v1/responses/compact` source handling by sending one terminal trigger to
  the source Responses endpoint and adapting its streamed compaction item to
  the existing JSON compact contract.
- Keep subscription-owned compact requests on the current account path, and
  fail closed for file pins, conflicting or unavailable ownership, disabled
  sources, and source credential changes.
- Preserve encrypted compaction output, upstream usage, source revision and
  exactly-once reservation/cleanup behavior across success, error and
  cancellation paths.

## Capabilities

### Modified Capabilities

- `model-source-routing`: source ownership and source credentials apply to
  Responses compaction as well as ordinary Responses turns.
- `responses-api-compat`: Codex and OpenAI-compatible compact routes use the
  source Responses trigger transport when the request is source-owned while
  preserving the subscription compact contract otherwise.

## Impact

Affected code is limited to Responses routing, source dispatch metadata and
compact response adaptation, with integration regressions at the public compact
and terminal-trigger routes. No new setting, credential, database migration or
upstream-specific model name is introduced.
