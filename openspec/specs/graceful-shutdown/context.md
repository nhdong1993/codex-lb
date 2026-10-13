# Graceful shutdown context

## Retryable WebSocket admission denial

The [requirements](spec.md) distinguish new upgrades from already admitted work.
A pre-accept WebSocket close is commonly rendered as HTTP 403 by ASGI servers,
making a temporary drain look like a permanent authorization error. Admission
therefore uses the existing HTTP-denial helper, returning 503 and Retry-After: 5.

For example, a new `/v1/responses/` upgrade during drain receives the OpenAI-style
`proxy_unavailable` envelope. `/ws/events` receives a generic detail body. Neither
invokes its handler or leaves an in-flight registration behind. An already
admitted Responses turn retains its finalization and reservation ownership until
completion or the existing shared drain deadline. No shutdown timeout, HA
rollout procedure, or active-session replay policy changes with this backport.
