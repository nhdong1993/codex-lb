# Standalone compaction stream contracts

The 2026-10-07 Codex review found three P2 defects; eight local fixture cases
demonstrated them before this correction. With `gpt-5-high` available only from
a non-streaming source and `gpt-5` from a streaming source, compact returned 503
while the equivalent terminal trigger succeeded. When SSE carried usage at the
event root or an earlier response event, compact returned 502 despite logging
21 input and 8 output tokens. A terminal error with numeric `code: 123` returned
500 and recorded cancellation rather than an upstream failure.

The selected corrections align compact selection with its actual streaming
transport, preserve source usage observations, and treat malformed provider
errors as upstream errors. For example, a terminal root usage object with
21 input / 8 output tokens must produce that usage in compact JSON and finalize
the same 29-token reservation. No error path may move retained state to another
credential. Existing mixed-ownership checks remain required.

The review evidence lives in `/tmp/compaction-readonly-review/`; the pre-fix
baseline is `/tmp/compaction-review-fixes-baseline/`. Permanent evidence belongs
in this change's verification document. All checks use local synthetic traffic.
