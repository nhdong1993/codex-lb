## ADDED Requirements

### Requirement: Python WSS connections reuse system verification context

The Python `websockets` fallback for upstream `wss://` connections MUST reuse a system-default SSL verification context across separate connections and outbound-client refreshes within one initialized application lifecycle. The context MUST preserve `ssl.create_default_context()` system/environment trust, certificate validation and hostname checking, and MUST NOT add the aiohttp client's certifi roots. Initialization MUST make the context available before ordinary request handshakes, and full outbound-client close followed by initialization MUST rebuild it from the then-current trust inputs. Plain `ws://` connections MUST receive no server-TLS context. Existing proxy resolution, native/routed transport selection and handshake cancellation cleanup MUST remain unchanged.

#### Scenario: Separate secure connections reuse the verification context
- **WHEN** multiple Python WSS connections open during one lifecycle, including after shared HTTP-client refresh
- **THEN** they use the same system verification context without rebuilding its trust store per handshake
- **AND** close followed by reinitialization uses a newly constructed system context

#### Scenario: Trust and hostname validation remain effective
- **WHEN** the Python WSS fallback connects to a server trusted by the configured system/default roots with a matching hostname
- **THEN** the TLS handshake succeeds
- **AND** an untrusted chain or mismatched hostname is rejected without disabling verification or adding certifi roots

#### Scenario: Plain WebSocket and cancellation behavior are preserved
- **WHEN** the Python fallback opens a `ws://` connection or its handshake is cancelled
- **THEN** a plain connection is not given an SSL context
- **AND** cancellation preserves the existing transport cleanup and propagation behavior

### Requirement: Responses HTTP preparation serializes only for active consumers

When the effective transport is unconditionally HTTP and the Python HTTP client does not need a pre-serialized body for an active consumer, Responses preparation MUST NOT serialize a full WebSocket-shaped request for a size decision that cannot affect that transport or serialize a full selected payload that no consumer uses. The transmitted HTTP body, metadata finalization and existing headers MUST remain unchanged. WS-eligible transport selection MUST retain its current exact-byte budget and fallback semantics. Enabled payload tracing, native request-body generation, archive ownership and payload-mutating fallback paths MUST retain their current contents and behavior.

#### Scenario: Python HTTP with inactive preparatory-string consumers
- **WHEN** a large Responses request uses explicit Python HTTP with raw payload tracing inactive
- **THEN** preparation performs no unused full-body serialization for WS size selection or an unused selected payload string
- **AND** the real upstream receives exactly the existing serialized HTTP body

#### Scenario: A consumer requires a serialized payload
- **WHEN** native transport, raw payload tracing or WS-eligible size/send handling requires a full payload string
- **THEN** the required serialization remains available with current contents
- **AND** payload changes before a later consumer are reflected without reusing stale bytes

#### Scenario: Auto image-generation requests are unconditionally HTTP

- **WHEN** an auto-transport Responses request includes an image-generation tool and uses the Python HTTP client with raw payload tracing inactive
- **THEN** preparation MUST skip full-body serialization for the unused WebSocket size decision, including when the request is below the WebSocket byte budget
- **AND** the real upstream MUST receive exactly the existing serialized HTTP body
