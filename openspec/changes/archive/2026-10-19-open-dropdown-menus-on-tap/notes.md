# Evidence

- Component test `src/components/ui/dropdown-menu.test.tsx`: on the baseline wrapper, a touch `pointerdown` alone opened the menu; with the change it stays closed and the following click opens it. Mouse, keyboard and controlled usage pass on both.
- Browser smoke (390x844, touch emulation): on the baseline, a 240 px swipe starting on the edit dialog's "All accounts" trigger opened the menu. With the change, the form scrolls, the menu stays closed, and a tap opens it.
- `Input.dispatchTouchEvent` drives the swipe. `Input.synthesizeScrollGesture` does not scroll in headless Chromium.
