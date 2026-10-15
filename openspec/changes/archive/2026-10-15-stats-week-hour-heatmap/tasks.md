# Tasks

## 1. Stats functions (inventory-app)

- [x] 1.1 Write failing tests in `src/stats.test.ts` for "Heat levels", "Local time zone" (Wednesday row), "No openings yet" (all-zero grid) and the 7-day filter used by "Older events only in the heatmap"; run `npm test -- src/stats.test.ts` and verify they fail
- [x] 1.2 Add `byWeekdayHour`, `heatLevel` and `lastDays` to `src/stats.ts`, and remove `perHour`, to make 1.1 pass

## 2. Stats screen (inventory-app)

- [x] 2.1 Write failing tests in `src/screens/Stats.test.tsx` for "Four weeks requested", "Older events only in the heatmap" and "Day and hour heatmap"; run them and verify they fail
- [x] 2.2 Request 28 days, filter to 7 days for the tiles and bar chart, and replace the hour strip with the heatmap to make 2.1 pass

## 3. Verify

- [x] 3.1 Run `npm test` and `npm run typecheck` in `pwa/`, all green
- [x] 3.2 Check the heatmap at 360 px wide in light and dark mode
