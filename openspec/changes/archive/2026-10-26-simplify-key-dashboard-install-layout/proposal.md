## Why

The Install tab spreads one task over a hero banner, four equally weighted cards, and a side column. The client chips look like buttons but do nothing, the platform tiles are tall, and on a 390-pixel phone the prerequisite ("Before you run") is pushed below every action, so holders reach the command and its requirements late.

## What Changes

- Replace the hero banner and its chips with a heading, description, and a plain-text list of supported clients.
- Show the prerequisite notice first.
- Put platform selection (compact radios), setup options (keep login and its warning), and the direct terminal command into one numbered primary section with Copy command as the primary action.
- Group script export and restoring the previous setup as secondary alternatives.
- Keep the guidance and key-privacy notes beside the steps on desktop and after them on mobile.
- No change to installer content, exports, masking, the keep-login warning, or the confirmation dialog.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-key-dashboard`: refine the installer presentation order and hierarchy.

## Impact

- Frontend only: `key-install-panel.tsx`, three locale files, the Install integration test, and the key-install screenshot spec (now also measuring page height and checking the expanded Windows preview at 390 pixels).
- No backend, API, or behavior change.
