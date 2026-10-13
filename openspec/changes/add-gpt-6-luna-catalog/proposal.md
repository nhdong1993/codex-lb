# Change: add-gpt-6-luna-catalog

## Why

The Codex model endpoint now advertises `gpt-6-luna`, but a cold or offline codex-lb instance has no bootstrap entry for it. Codex CLI therefore cannot discover the model until a successful account refresh supplies the live catalog.

## What Changes

- Add a bootstrap `gpt-6-luna` catalog entry mirrored from the upstream Codex models endpoint.
- Advertise the model to the `free` plan and preserve subscription/source catalog separation.
- Keep live endpoint snapshots authoritative once fetched.

## Impact

This is an additive model-catalog change. No source-model entry is added and no existing account-selection path is changed for models absent from the catalog.
