## Decisions

Accept the existing compact request type in shared selection/continuity and
ownership-miss helpers. Read its retained references without converting it into
Responses or running subscription trimming. File pins and recorded subscription
owners take precedence; only a selected source requires `source_compact_request`.
Do not catch source validation failures and silently fall back to an account.

Catch aiohttp transport errors at the compact collector boundary. Preserve the
opened stream's upstream status and keep connection-failure replay disabled.
Use the existing dispatch error finalizer to close transport, release admission
and usage reservations, and record the actual source/revision and error status.
Timeout and cancellation retain their separate handling.

## Validation

Use a local HTTP upstream that emits a first event and then aborts TCP. Assert
502, an OpenAI error envelope, one source attempt, error logging and released
reservation/admission on both endpoints. Verify compact extras reach the
subscription service with no source, with a shadowing source and a recorded
subscription owner, and with file pins. Source-owned invalid Responses fields
still fail before dispatch; disabled/unavailable source ownership still denies.
