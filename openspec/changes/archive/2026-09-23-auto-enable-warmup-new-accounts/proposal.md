## Why

Newly authenticated accounts currently require a separate warm-up toggle even when the operator already uses fleet warm-up. Automatically enrolling new accounts keeps them eligible for the existing idle-quota wakeup mechanism.

## What Changes

- Enable the account warm-up flag when OAuth or auth.json import creates a new account.
- Preserve the existing account's flag on reauthentication and credential replacement, including an explicit opt-out.
- Keep the global warm-up switch, quota eligibility, stagger, cooldown, and durable attempt claims unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `usage-refresh-policy`: Newly authenticated or imported accounts automatically enroll in limit warm-up; existing preferences survive credential replacement.

## Impact

The OAuth and account-import services initialize the existing account field. Integration tests cover the dashboard auth/import routes and retained preferences. No schema migration, new setting, or immediate probe during authentication is required.
