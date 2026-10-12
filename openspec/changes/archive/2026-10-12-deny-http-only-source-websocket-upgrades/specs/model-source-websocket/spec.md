## ADDED Requirements

### Requirement: Source-only handshakes honor effective HTTP-only capability

After successful authentication and firewall admission, ordinary Responses WebSocket handshakes for a source-only API key SHALL evaluate the same effective permitted model pool as its client installer. If that pool is empty or any eligible model is not fully streaming and WebSocket-capable, the service MUST return HTTP 426 with the existing `websocket_upstream_transport_unavailable` envelope before accepting the socket, reserving usage or connecting upstream. A fully capable source-only pool MUST retain WebSocket admission subject to existing transport policy. This rule MUST apply to both public Responses route families and trailing-slash variants. Mixed subscription/source and unrestricted keys MUST retain existing handshake policy. Required-capability routing MUST retain its existing WebSocket exception. A capability lookup failure MUST return a sanitized retryable HTTP 503 without accepting the socket or exposing internal failure details.

#### Scenario: HTTP-only source forces immediate transport fallback

- **GIVEN** an authenticated source-only key assigned an HTTP-only Responses model
- **WHEN** a client requests a Responses WebSocket upgrade
- **THEN** the upgrade is rejected with HTTP 426 before any upstream attempt or usage reservation
- **AND** an authorized HTTP request for that model continues to work

#### Scenario: Capable source pool retains WebSocket

- **GIVEN** a source-only key whose effective permitted models all support streaming WebSocket
- **WHEN** an ordinary upgrade arrives and global transport permits WebSocket
- **THEN** the connection is accepted under the existing source routing policy

#### Scenario: Mixed key cannot be inferred from a later model frame

- **GIVEN** a key with both subscription accounts and an HTTP-only source
- **WHEN** a model-less upgrade arrives
- **THEN** this source-only rule does not downgrade the key's subscription sessions

#### Scenario: Lookup failure is not evidence of HTTP-only capability

- **GIVEN** source capability lookup raises a database error or timeout
- **WHEN** a source-only handshake is evaluated
- **THEN** the service returns sanitized HTTP 503 without credentials or driver details

#### Scenario: Authentication precedes fallback

- **GIVEN** an invalid API key
- **WHEN** the client requests an upgrade
- **THEN** the normal authentication denial is returned instead of HTTP 426
