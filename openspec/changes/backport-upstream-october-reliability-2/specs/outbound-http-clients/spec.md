## MODIFIED Requirements

### Requirement: Enabled model schedulers warm client identity on every replica

Every replica with model refresh enabled MUST refresh its process-local Codex client-version cache independently of model-refresh leadership. Outbound non-native fingerprints MUST read the warmed cache without network I/O on the request path. Lookup failure MUST preserve cached or configured fallback behavior and MUST NOT prevent the subsequent model refresh or follower reconciliation. Scheduler shutdown MUST cancel and await a pending warmup. The unconfigured fallback MUST be at least the highest `minimal_client_version` declared by the bootstrap model catalog (currently `0.163.0`; gpt-6-luna requires `0.155.0`); explicit operator overrides MUST remain respected.

#### Scenario: Follower forwards the warmed version

- **WHEN** a follower refresh tick discovers client version 9.9.9
- **THEN** a subsequent non-native outbound request uses 9.9.9 in User-Agent and version
- **AND** the follower does not perform leader-only account model discovery

#### Scenario: Lookup failure does not stop reconciliation

- **WHEN** a replica's client-version lookup fails
- **THEN** its model refresh or follower reconciliation still runs
- **AND** outbound requests retain the cached or configured fallback version

#### Scenario: Shutdown cancels pending warmup

- **WHEN** the scheduler stops while its version lookup is pending
- **THEN** the lookup task is cancelled and awaited without a detached background task

#### Scenario: Fallback covers every bootstrap model

- **GIVEN** no operator override for the client version and a failed or not-yet-warmed version lookup
- **WHEN** the replica presents its fallback client version
- **THEN** that version is at least every `minimal_client_version` in the bootstrap catalog
- **AND** a degraded-startup model refresh still receives gpt-6-luna

### Requirement: Native TLS dependencies exclude the known handshake-level advisory

The locked native egress dependency graph MUST use Rustls 0.23.46 or a compatible patched release, excluding the versions affected by RUSTSEC-2026-0285 and RUSTSEC-2026-0346 through RUSTSEC-2026-0349. The AWS-LC dependency family MUST resolve compatibly in locked builds. The upgrade MUST preserve native protocol negotiation, TLS verification, WebSocket behavior, and fork queue byte budgets.

#### Scenario: Reproducible patched helper
- **WHEN** the native helper is built with the committed lockfile
- **THEN** Rustls resolves to the patched version and packaging assertions agree with the lockfile
- **AND** native transport and WebSocket regression tests remain valid

## ADDED Requirements

### Requirement: Locked Python dependencies exclude the known urllib3 advisories

The project MUST require urllib3 2.8.0 or later in its manifest and MUST lock a version that satisfies that floor, so the runtime image is free of CVE-2026-97687 and CVE-2026-97689. The package version of codex-lb MUST NOT change as part of this dependency update.

#### Scenario: Frozen install resolves the patched urllib3
- **WHEN** the runtime environment is installed from the committed lockfile
- **THEN** urllib3 resolves to 2.8.0 or later
- **AND** the lockfile remains consistent with the manifest

### Requirement: Runtime image upgrades installed Debian packages with security fixes

The runtime image build MUST upgrade the already-installed base packages that carry published high-severity Debian security fixes, including `gzip`, `libpcre2-8-0`, `libsqlite3-0` and `perl-base`, using an upgrade-only install so that no package absent from the base image is added.

#### Scenario: Runtime stage upgrades the vulnerable base packages
- **WHEN** the runtime image is built from the committed Dockerfile
- **THEN** the upgrade-only package step includes `gzip`, `libpcre2-8-0`, `libsqlite3-0` and `perl-base`
- **AND** the base image and the set of installed packages are otherwise unchanged
