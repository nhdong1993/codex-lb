# Context: warn-default-source-context-window

## Incident (2026-10-16)

Thread `01a13e8a…` (key `cto_vupqh`) ran on `gpt-6.1-sol` up to 238,047 input tokens at 08:17:23Z. The user then switched the thread to `http/gpt-6-astra` (source `ch-relay (VPS)`) and asked Codex to compact. The compact failed in Codex Desktop. No request from that thread reached codex-lb afterward: request logs, all three HA slots and HAProxy showed nothing.

The `http/gpt-6-astra` row had `context_window = NULL` and no `auto_compact_token_limit`. `app/modules/model_sources/catalog.py` substitutes `DEFAULT_SOURCE_CONTEXT_WINDOW = 128_000` in that case and also uses it as `max_context_window`. Codex sized the thread against 128,000 tokens. Other clients had already sent up to 213,812 input tokens to the same model successfully. Sibling `ch/gpt-6-astra` rows on other sources declared 272,000 tokens with `auto_compact_token_limit: 244800`.

The operator fixed the five rows of that source by hand (272,000 for `gpt-6-astra`/`gpt-6-sol`, 500,000 for `gpt-6.1-sol`, matching the subscription registry). This change makes the trap visible in the dashboard.

## Decisions

- **Frontend constant instead of an API field.** The default is a fixed backend constant, not runtime configuration. Mirroring it in `model-source-form.ts`, with a comment pointing at `catalog.py`, avoids widening the `/api/model-sources` contract for a hint. If the backend default changes, both constants change in the same commit.
- **Only enabled models count.** Disabled models are not advertised in the catalog, so their missing window cannot affect a client.
- **Warn on every source, enabled or not.** A disabled source is usually re-enabled later. The hint costs nothing while it is off.
- **Advisory only.** Some local or small models really have a 128,000-token or smaller window. Blocking a blank field would force operators to type the default.

## Example

A source with `http/gpt-6-astra` (no window), `http/gpt-6-sol` (272,000) and a disabled `http/old` (no window) shows one warning:

> No context window set for http/gpt-6-astra. Codex is told this model accepts 128,000 tokens, so longer threads fail to compact. Set the real window in Edit.

## Failure modes

- A source whose first model declares a window while later models do not: the edit form shows a value, so the form hint stays hidden. The list warning still names the models without a window. Saving the form with a changed value applies it to every model.
