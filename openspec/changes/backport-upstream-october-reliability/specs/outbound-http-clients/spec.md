## ADDED Requirements

### Requirement: Native TLS dependencies exclude the known handshake-level advisory

The locked native egress dependency graph MUST use Rustls 0.23.45 or a compatible patched release, excluding the versions affected by RUSTSEC-2026-0285. The AWS-LC dependency family MUST resolve compatibly in locked builds. The upgrade MUST preserve native protocol negotiation, TLS verification, WebSocket behavior, and fork queue byte budgets.

#### Scenario: Reproducible patched helper
- **WHEN** the native helper is built with the committed lockfile
- **THEN** Rustls resolves to the patched version and packaging assertions agree with the lockfile
- **AND** native transport and WebSocket regression tests remain valid
