## Why

Radix `DropdownMenu.Trigger` opens its menu on `pointerdown` for every pointer type. On a phone, `pointerdown` fires as soon as a finger lands, before the browser decides whether the gesture is a tap or a scroll. A swipe that starts on any dashboard dropdown trigger therefore opens the menu, and the modal menu blocks the scroll the operator wanted. The API key create/edit dialogs stack five such triggers (Allowed models, Assigned accounts, Assigned model sources, Usage sections, Allowed efforts), so scrolling those forms on a phone keeps popping menus open. Radix `Select` already avoids this by opening touch interactions on click.

## What Changes

- The shared `DropdownMenuTrigger` wrapper skips Radix's `pointerdown` opening for touch pointers and toggles the menu on the tap's `click` instead. A touch that becomes a scroll never produces a click, so the menu stays closed.
- Mouse and keyboard opening keep the existing Radix behavior.
- The shared `DropdownMenu` wrapper owns the open state (still honoring controlled `open`/`onOpenChange`) so its trigger can toggle on tap.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-architecture`: Dashboard dropdown menus open on a completed tap, not when a touch scroll starts.

## Impact

- Affected component: `frontend/src/components/ui/dropdown-menu.tsx` (every dashboard dropdown menu).
- Affected tests: dropdown wrapper component test and browser-smoke touch coverage.
- No API, schema, persistence or configuration changes.
