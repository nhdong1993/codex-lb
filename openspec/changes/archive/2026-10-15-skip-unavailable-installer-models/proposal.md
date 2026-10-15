# Proposal

## Why

Exported installers configure the enforced model or only the first allowed model and stop with "The configured model is unavailable" when that slug is absent from the key's list-visible catalog. Allowlists routinely start with hidden helper models such as `codex-auto-review` or with models the upstream registry later retires (for example `gpt-5.4-mini`), so setup fails even though the key can use other catalog models. On 2026-10-14 this blocked setup for five production keys.

## What Changes

- Export the enforced model, otherwise every allowed model in configured order, as ordered model preferences instead of a single default.
- At each run, the Bash/Python and PowerShell installers skip preferences that are absent from the retained catalog and configure the first remaining preference; when none remains they configure the first retained catalog model.
- Report skipped preferences and the configured model on stderr. An empty retained catalog still stops setup before replacement.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-key-dashboard`: Installer default-model selection skips models that are not in the key's catalog instead of stopping setup.

## Impact

Changes are confined to installer export/rendering, installer tests, and the owning OpenSpec capability. No settings, dependencies, migrations, or dashboard UI changes. Previously exported scripts keep their embedded selection program; users must export a new installer to receive the fallback.
