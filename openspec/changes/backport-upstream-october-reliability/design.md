## Context

This is a five-fix backport onto fork HEAD `67294897`, not a beta release merge. The workspace contains unrelated edits and overlapping warmup/isolation changes. Baseline patches and overlapping files are recoverable under `/tmp/codex-lb-october-backports.Oq5y1C`.

## Goals / Non-Goals

Goals: patched native TLS and the four requested externally visible reliability fixes with route-level regressions. Non-goals: importing auth/overflow migrations, UI work, extra routing features, release version changes, commit, push, or deploy.

## Decisions

- Use the dependency-only portion of #2453 plus #2454's packaging assertions; do not import unrelated Nix/CI edits.
- Port #2496, #2119, and #2255 with their regression tests. Existing quota precedence, disabled-account guards, probe refresh, and drain accounting stay unchanged.
- Port #2449's shared normalized usage predicate and each consumer rather than widening all server errors. Preserve the fork's narrow OpenAI processing-error isolation and settlement-first change.
- Use focused patch edits, not cherry-pick/merge over the dirty checkout. Test with isolated synthetic databases and no production env file. Prefer existing upstream test cases plus fork preservation checks.
- Keep all requirements in delta specs and rationale here/context. Do not overwrite entire canonical files with upstream versions.

## Risks / Trade-offs

- Concurrent and uncommitted work → snapshot overlapping files, retain unrelated hunks, and inspect task-only diffs.
- Message-based quota false positives → permit only normalized upstream_error or the explicit quota code; test explicit-code precedence and unrelated messages.
- Fork ownership/settlement regression → route-level HTTP/WebSocket tests plus existing source, file-pinning, isolation, and settlement regressions.
- Native dependency ABI/build drift → locked Rust build/tests and packaging/native adapter tests; preserve toolchain and protocol.
- Upstream tests depending on later releases → adapt only harness seams required for the frozen fork, documenting deviations.
- Scope remains HTTP streaming and direct WebSocket quota recognition; no new HTTP-bridge replay policy or broader account-pool walk is introduced.

## Migration Plan

No database migration or production mutation. A later separately authorized HA rollout builds the new helper from the lockfile. Full beta.9/10 upgrade remains separate because its column-drop migrations are not rolling-safe.

## Open Questions

None required before implementation. Any test limitation will be recorded in verification rather than counted as a pass.
