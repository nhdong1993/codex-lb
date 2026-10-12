## Context

The shared error-health funnel already records overload failures after request settlement. OpenAI processing failures reach the same funnel with `server_error` and the message observed on 2026-09-16: “An error occurred while processing your request. You can retry your request, or contact us through our help center at help.openai.com if the error persists.” A request ID may follow.

## Goals / Non-Goals

**Goals:** Feed that recognized upstream signature into the existing success-independent backoff/isolation window; preserve generic errors and all routing/settlement contracts.

**Non-Goals:** Shared replica counters, changed thresholds, automatic persisted PAUSED status, new settings, retries, or ownership changes.

## Decisions

- Use a pure code-and-message predicate alongside the existing overload code set. Keep that code set unchanged because retry normalization also uses it.
- Require `server_error` plus the two canonical processing-error/help-center sentences. Match case and whitespace insensitively; accept the bare help-center domain or its HTTPS URL. A trailing upstream request ID is optional. A domain mention alone or a lookalike domain is insufficient.
- Call the predicate at the existing health-write hook, preserving deferred API-key settlement and failure envelopes. Matching failures share the overload window; successes do not reset it.
- Terminal-stream regression coverage exposed a detached-settlement path on startup-probe closure. Treat a pending account-health error as requiring confirmed settlement in the shared settlement helper before any health write. Unconfirmed settlement continues to suppress the health write.
- Keep existing health eligibility: failures after visible text and account-neutral disconnects do not acquire a new penalty through this predicate.
- Use route regressions for HTTP error bodies and streamed terminal failures, alongside the existing ownership/backoff tests.

## Risks / Trade-offs

- OpenAI may change its message → unmatched messages keep generic transient handling until a new observed signature is added.
- This is message recognition, not cryptographic proof of origin → only evaluate the structured upstream error at the existing health funnel.
- Replica-local thresholds and soft pool fallback still apply → this patch expands recognized evidence without promising a global hard pause.
