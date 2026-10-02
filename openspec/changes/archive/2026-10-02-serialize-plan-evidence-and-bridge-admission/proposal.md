## Why

Review reproduced a delayed first-Free enqueue invalidating a newer confirming sample, an excluded cached account blocking a different healthy file owner, and a local evidence-read failure closing an accepted bridge sibling and penalizing account health.

## What Changes

- Permit first-Free enqueue only while the shared first observation still awaits confirmation; preserve generation after that evidence is consumed or superseded.
- Apply cached model exclusion to the request's actual required owner, allowing selection of a different healthy file owner.
- Classify bridge model-evidence database failures as sanitized, pre-dispatch admission errors with request-local cleanup.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `usage-refresh-policy`: delayed enqueue must not invalidate consumed confirmation evidence.
- `account-routing`: owner-specific exclusion and local model-admission failure isolation.

## Impact

Priority-check enqueue, HTTP bridge reuse and submission, focused integration tests and specifications. No schema, configuration or UI change.
