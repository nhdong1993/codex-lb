## 1. Regression coverage

- [x] 1.1 Add a browser-smoke regression that opens the edit dialog from `/apis` at 320x568, 390x844 and 1440x900 and proves the viewport-bounded shell, one internal scroll region, persistent title/Close/Save and field reachability.
- [x] 1.2 Record that the baseline layout fails the regression before the implementation change.

## 2. Dialog layout

- [x] 2.1 Convert the edit dialog to the viewport-bounded flex-column shell with a persistent header and footer.
- [x] 2.2 Move the responsive form grid into one `min-h-0` internal scroller and drop the per-column scroll constraints.

## 3. Verification

- [x] 3.1 Run the focused edit-dialog component tests plus frontend lint and typecheck.
- [x] 3.2 Run the browser-smoke suite and validate the OpenSpec change.
