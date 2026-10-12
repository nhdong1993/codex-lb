## Context

The source capability and installer already calculate a conservative effective model pool. The ordinary handshake guard currently checks only the global transport and recent subscription transport failures. The first request model arrives after upgrade, so unrestricted mixed keys cannot be downgraded selectively by that model at handshake time.

## Goals / Non-Goals

Make a source-only key's live handshake honor its installer transport capability. Do not claim arbitrary clients must honor HTTP 426, downgrade a mixed key globally, translate WS turns to HTTP, or replay accepted state.

## Decisions

- Reuse `source_only_key_supports_websockets`, including aliases, enforcement, source/key scoping and global policy. A capable-only pool keeps WebSocket; an empty or mixed-capability source-only pool uses HTTP, as its installer already specifies.
- Return the existing sanitized 426 envelope before accepting, reserving usage or connecting upstream. Authentication, firewall and required-capability exceptions retain precedence.
- Leave mixed/unrestricted keys unchanged: use a dedicated HTTP provider (`supports_websockets=false`) for HTTP-only source models, or assign a separate source-only key.
- Update the known HTTP-only ch-relay capability through the supported model-source service when applying operator configuration; never rewrite its model list or credentials.

## Risks / Trade-offs

Source-only handshakes add a source catalog read. Lookup failure must fail closed with a sanitized retryable 503, not masquerade as transport incompatibility. A key containing both HTTP and WS sources chooses HTTP for the session, consistent with installer behavior. Codex HTTP fallback persists for the client session.

## Migration Plan

No migration. Setting an HTTP-only source's native-WebSocket flag false updates catalogs and newly generated installers immediately on existing code. The new live handshake behavior requires a separately authorized rollout. Existing client configuration/cached sessions may require a restart or regenerated installer.
