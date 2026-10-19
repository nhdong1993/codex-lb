# Evidence

Measured at 390x844 with touch emulation (`Input.dispatchTouchEvent` swipes; `synthesizeScrollGesture` does not scroll in headless Chromium).

- Before: three vertical scrollers — dialog shell (810/1192 px), General column (464/1116 px) and Limits column (463/780 px). Six swipes from the middle of the dialog scrolled only the Limits column (stopped at 317 px, `overscroll-contain`). The shell never moved and Save stayed below the fold.
- Before (browser smoke, 320x568): Save button bottom edge at 704 px.
- After: one scroller (`api-key-edit-scroll-region`, 643/1925 px). Swipes reach the end of the form (scrollTop 1282) and Save stays visible throughout.

## Related changes

A swipe that started on a dropdown trigger in this form still opened the menu (Radix `DropdownMenuTrigger` opens on `pointerdown`). That is fixed separately in `open-dropdown-menus-on-tap`.
