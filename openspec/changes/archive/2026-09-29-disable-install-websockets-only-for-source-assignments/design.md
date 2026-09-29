# Design

## Context

See [proposal.md](proposal.md) for motivation. Installer export already authenticates the key and has its account/source assignments. Native catalog metadata is not an assignment inventory: source-only keys can still receive native entries, including collisions with source model names.

## Goals / Non-Goals

Apply the assignment policy consistently to the three exported platforms while preserving catalog downloads, metadata, validation, backups, and uninstall behavior. Routing and model discovery stay outside this change.

## Decisions

- Compute a boolean from the authenticated key at export: disable only when the source assignment list is nonempty and the account assignment list is empty.
- Pass the boolean into the shared config renderer, alongside the existing endpoint and selected model, and remove catalog programs' transport override. This keeps Bash and PowerShell consistent and does not expose assignment IDs.
- Do not infer assignments using `all` or `any` over model preferences. Neither identifies source-only keys reliably.

## Risks / Trade-offs

- Saved installers capture assignment policy at export, like their default model and key. After assignments change, download/copy a fresh installer. Existing files are not edited remotely.
- Enabling provider WebSockets does not change the catalog's per-model preference or add WebSocket support to model sources.

## Migration Plan

No database or configuration migration. Run a newly exported installer to apply the policy; existing backup and offline uninstall behavior is preserved.
