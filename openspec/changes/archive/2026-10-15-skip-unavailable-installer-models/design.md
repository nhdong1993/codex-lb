# Design

## Context

See [proposal.md](proposal.md). The catalog served by `/api/key-dashboard/models` is already scoped to the key: unlisted or non-API entries are removed by the installer, and list-visible entries are a subset of the key's permitted models. Model availability changes over time (upstream retirement, hidden helper models), while an exported script lives on.

## Decisions

- Export ordered preferences (`preferred_models`) rather than a single `model`: `[enforced_model]` when enforced, else the allowlist in stored order, else empty. Order is the administrator's existing allowlist order, so no new setting is needed.
- Resolve the default at run time against the freshly downloaded catalog, so re-running an old export after a catalog change keeps working.
- Fall back to the first retained catalog entry when no preference remains. This matches the existing unrestricted-key behavior and stays inside key scope because the catalog is key-scoped.
- Print skipped preferences and the chosen model to stderr as JSON-quoted strings, keeping stdout unchanged and neutralizing control characters. The credential is never printed.

## Risks / Trade-offs

- A user may get a different default than the administrator intended when the intended model disappears; the stderr notice makes this visible and clients can still switch models.
- Old exported scripts keep the strict check until a new installer is exported.

## Migration Plan

No database or configuration migration. Deploy, then export and run a new installer.
