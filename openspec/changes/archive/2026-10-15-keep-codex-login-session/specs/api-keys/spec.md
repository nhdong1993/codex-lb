## ADDED Requirements

### Requirement: Dedicated API-key header for proxy authentication

Proxy authentication SHALL accept the API key from the `X-Codex-LB-Api-Key` request header. When that header is present and nonblank it MUST take precedence over `Authorization` on proxy HTTP, WebSocket, required-capability and Codex usage-identity authentication, and an invalid value MUST be rejected without falling back to `Authorization`. The system MUST NOT forward this header upstream and MUST NOT store, validate or forward the `Authorization` value of a request authenticated by it; when a request is forwarded to another codex-lb replica, the forwarded credential MUST be the API key. Key self-service endpoints, including the key dashboard, installer export and `/v1/usage`, MUST continue to accept only the `Authorization` Bearer API key.

#### Scenario: Client keeps its own login token in Authorization

- **GIVEN** a request whose `Authorization` carries a client login token and whose `X-Codex-LB-Api-Key` carries an active API key
- **WHEN** it calls a proxy route, opens a proxy WebSocket, or requests Codex usage
- **THEN** it is authenticated as that API key
- **AND** the upstream request carries neither the login token nor the API-key header

#### Scenario: Dedicated header takes precedence

- **WHEN** `X-Codex-LB-Api-Key` holds an invalid key and `Authorization` holds a valid key
- **THEN** the request is rejected with 401

#### Scenario: Self-service ignores the dedicated header

- **WHEN** a key-dashboard endpoint receives the key only in `X-Codex-LB-Api-Key`
- **THEN** it rejects the request with 401
