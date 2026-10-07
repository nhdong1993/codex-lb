## 1. OpenSpec and routing contract

- [x] 1.1 Add delta requirements for source-owned compaction, subscription
  ownership precedence, trigger transport, output/usage preservation and
  fail-closed cleanup.
- [x] 1.2 Validate the change artifacts and keep the existing model-source and
  Responses compatibility contracts consistent with the delta.

## 2. Implementation

- [x] 2.1 Allow Codex terminal compaction triggers to use normal source
  selection while retaining file and subscription-owner exclusions.
- [x] 2.2 Route standalone compact requests through a source Responses stream
  with a single terminal trigger and normalize its encrypted compaction output
  to the existing compact JSON response.
- [x] 2.3 Preserve source aliasing, ownership publication, usage settlement,
  request-kind/source-revision logging and cancellation cleanup.

## 3. Regression coverage

- [x] 3.1 Cover `/backend-api/codex/responses`, `/v1/responses`, both compact
  endpoints and trailing-slash variants through the public API paths.
- [x] 3.2 Cover subscription compact regression, source disabled/owner conflict,
  encrypted output and usage/cleanup behavior.

## 4. Verification

- [x] 4.1 Run focused tests, lint/type checks applicable to touched files and
  strict OpenSpec validation; record results in verification notes.
