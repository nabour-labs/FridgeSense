# Tasks

## 1. Duration formatting

- [x] 1.1 Write a failing test "Minutes and seconds" in `pwa/src/format.test.ts` for `duration(0|45|59|60|65|600)`. Run `npm --prefix pwa test -- format` and see it fail on the missing export
- [x] 1.2 Implement `duration` in `pwa/src/format.ts`; verify 1.1 passes

## 2. Per-day duration summary

- [x] 2.1 Write failing tests in `pwa/src/stats.test.ts` for `durationStats`: "Today's open times" (20/30/40 → 30/40/20 and yesterday 25/35 → 30/35/25), "Average rounded", "Single opening", "Day without openings" (null) and "Open time in local days". Run `npm --prefix pwa test -- stats.test` and see them fail
- [x] 2.2 Implement `durationStats` in `pwa/src/stats.ts`; verify 2.1 passes

## 3. Open time card

- [x] 3.1 Write failing tests in `pwa/src/screens/Stats.test.tsx`: "Today's open times", "Pick another day", "Seven day buttons", "Long opening on the card", "Day without openings". Run `npm --prefix pwa test -- Stats.test` and see them fail on the missing "Open time" figure
- [x] 3.2 Add the "Open time" card with 7 day buttons and Average / Longest / Shortest tiles to `Stats.tsx`; verify 3.1 and the existing Stats tests pass
- [x] 3.3 Check the `pwa-mock` preview at 375 px and desktop: card fits without horizontal scroll, buttons switch the values

## 4. Wrap-up

- [x] 4.1 Run `npm --prefix pwa test` and `npx --prefix pwa tsc --noEmit -p pwa` green
