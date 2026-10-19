## 1. Regression coverage

- [x] 1.1 Add an APIs page component test: stacked-layout selection scrolls the detail panel into view, desktop selection does not.
- [x] 1.2 Add a browser-smoke phone regression: the Detail-view selector is not an internal scroller and tapping a key brings that key's detail panel into the viewport.

## 2. Implementation

- [x] 2.1 Limit the Detail-view selector's bounded scroll region to the desktop breakpoint.
- [x] 2.2 Scroll the detail panel into view after a Detail-view selection below the desktop breakpoint, honoring reduced motion and the sticky header.

## 3. Verification

- [x] 3.1 Run the APIs component tests, frontend lint and typecheck.
- [x] 3.2 Run the browser-smoke suite and validate the OpenSpec change.
