## 1. Regression coverage

- [x] 1.1 Add a component test proving touch `pointerdown` alone does not open the menu, a touch tap opens it, and mouse/keyboard opening is unchanged.
- [x] 1.2 Add a browser-smoke touch regression on `/apis`: a swipe that starts on an edit-dialog dropdown trigger scrolls the form and leaves the menu closed, and a tap opens it.

## 2. Implementation

- [x] 2.1 Make the shared `DropdownMenu` wrapper hold open state while honoring controlled props, and expose a tap toggle to its trigger.
- [x] 2.2 Make `DropdownMenuTrigger` skip Radix `pointerdown` opening for touch and toggle on the following click.

## 3. Verification

- [x] 3.1 Run the dropdown and dropdown-consuming component tests, frontend lint and typecheck.
- [x] 3.2 Run the browser-smoke suite and validate the OpenSpec change.
