## 1. Implementation

- [x] 1.1 Add a narrow OpenAI server-error predicate and wire it into the existing settled health-write path.
- [x] 1.2 Add positive/negative message coverage and public-route regressions for HTTP and streamed failures, including success-independent escalation.

## 2. Verification

- [x] 2.1 Run relevant proxy/backoff/ownership/settlement tests and lint/type checks.
- [x] 2.2 Sync requirements and stable context, validate OpenSpec and verify the change for archive.
