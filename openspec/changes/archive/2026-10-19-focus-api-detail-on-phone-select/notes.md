# Evidence

- Baseline at 390x844: the Detail-view selector was an internal scroller (588 of 1408 px for 14 keys), and tapping a key left the page at the list with the detail panel below the fold.
- With the change, the selector flows with the page below `lg`, and tapping a key places its detail heading directly under the sticky header. At 1440x900 the selector keeps its bounded scroller and selection does not scroll.
- Covered by `apis-page.test.tsx` (stacked versus desktop selection) and the browser-smoke phone test. Both fail on the baseline.
