## Why

On 2026-10-16, a Codex Desktop user could not compact a ~238k-token thread after switching it to `http/gpt-6-astra`. The compact never reached codex-lb. The source model had no stored context window, so the model catalog advertised the source default of 128,000 tokens (`DEFAULT_SOURCE_CONTEXT_WINDOW`). Codex therefore treated the thread as larger than the model's window. The real model accepts 272,000 tokens.

The dashboard gives no hint that a blank Context Window field means "advertise 128,000 tokens". Operators leave it blank because it looks optional, and the failure only shows up later on the client.

## What Changes

- The model source list shows a warning on every source that has enabled models without a context window. The warning names those models and states the 128,000-token default the catalog advertises for them.
- The create and edit source forms show the same default under the Context Window field while the field is blank.
- The warnings are advisory. They never block saving and never change stored values.

## Capabilities

### Modified Capabilities

- `model-source-routing`: Add a dashboard requirement that surfaces the default context window for source models that do not declare one.

## Impact

- Frontend: `features/model-sources` list and form fields, one shared helper and constant, en/ko/zh-CN strings and tests.
- Backend, API contract, routing and catalog behavior stay unchanged. No migration, no new `CODEX_LB_*` setting and no new dashboard navigation item.

## Non-goals

- Changing the 128,000-token default or inferring a window from the upstream model ID.
- Per-model context-window editing. The form still applies one context window to every model of the source.
- Repairing existing rows. Operators fill in the field from the warning.
