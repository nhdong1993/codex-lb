## Why

The latest compaction review reproduced three failures on both standalone
endpoints: alias selection ignores streaming capability, valid stream usage is
lost outside the terminal response, and malformed upstream error fields escape
as HTTP 500/cancelled. Equivalent Responses trigger requests succeed in the
first two cases. These gaps prevent compatible sources from compacting reliably.

## What Changes

- Select compact sources and probe disabled sources with streaming required.
- Retain validated observed usage when the terminal response omits usage,
  including large events, without buffering history or changing settlement.
- Translate error-envelope validation failures to the existing upstream 502
  path, preserving cancellation and avoiding replay after submission.
- Add API regressions, validate, run the authorized Codex review loop, and archive.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-source-routing`: standalone compaction stream selection, usage and errors.

## Impact

Proxy compact routing/collection and source compact integration tests. No new
settings, migrations, credentials, commits or deployment are included.
