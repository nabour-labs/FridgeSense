# Tasks

## 0. Base spec

- [ ] 0.1 Archive `firetv-kitchen-dashboard` (mark 4.1 done: it ran on the Vega Virtual Device with live data) so `openspec/specs/tv-dashboard/` exists; verify with `openspec validate tv-dashboard-more`

## 1. TV helpers (`pwa/src/tv/tv.ts`)

- [ ] 1.1 Write failing tests in `tv.test.ts` for "Time and duration", "No-change openings collapse", "Single no-change opening", "Analysis running", "Newest five", "Change labels" and "Older openings ignored" (`recentRows` with a time zone, `clockTime`); run `npx vitest run src/tv` and see them fail
- [ ] 1.2 Implement `clockTime` and the new `recentRows` (7-day cut, time, duration, collapse before taking 5) until 1.1 passes
- [ ] 1.3 Write failing tests for "Out of stock", "Many out of stock" and "Nothing out of stock" (`outOfStock`), "Open time today" and "No openings today" (`opensSummary` with open time), and "Heatmap" (cell labels and levels); confirm they fail
- [ ] 1.4 Implement `outOfStock`, the open time in `opensSummary`, and `heatCells` (reusing `byWeekdayHour` and `heatLevel`) until 1.3 passes
- [ ] 1.5 Write failing tests for "Camera online", "Camera offline", "Ring unavailable" and "Monitoring paused" (`cameraLine`), and "Condiment on the TV" and "Pepper on the TV" (`tvIcon`); add "Phone unchanged" to `src/itemIcon.test.ts`; confirm the new ones fail
- [ ] 1.6 Implement `cameraLine` and `tvIcon` until `npx vitest run src/tv src/itemIcon.test.ts` passes

## 2. TV dashboard (`pwa/src/tv/TvDashboard.tsx`)

- [ ] 2.1 Write failing tests in `TvDashboard.test.tsx` for "Four weeks requested", "Only three endpoints", "Camera image not shown", "No controls", "Camera fails, panels load", "Camera refresh" (fake timers: no request at 30 s, one at 5 min), "Updated after load", "Nothing loaded yet", "Pointer hidden", and the out-of-stock line, collapsed rows, open time, heatmap and TV icons rendered; update the old "Only two endpoints" test to three; confirm they fail
- [ ] 2.2 Implement them: `events(28)`, the camera `useLoad` (5 min), the header with "Updated" and the camera line, the out-of-stock line, timeline rows, open time, shorter bars and the heatmap, `tvIcon`, `cursor-none`; until `npm test` in `pwa/` passes, with the existing scenarios ("Items by category", "More than fits", "Empty fridge", "Inventory refresh", "Events fail, inventory loads", "Session expired on the TV", "Stills not shown", "Back is left to the TV app") still green
- [ ] 2.3 Check the layout at 1920×1080 in the browser preview (`pwa-mock`, `#tv`): nothing overflows its panel, the heatmap is readable; take a screenshot

## 3. On the TV

- [ ] 3.1 After the PWA deploy (ask first), relaunch the Fire TV app on the Vega Virtual Device and check: 🧂 for condiments, no cursor over the panels, camera line, heatmap. If the cursor still shows, add a friction-log entry (design.md decision 6)
- [ ] 3.2 Update the README's Fire TV section with what the dashboard shows

## 4. Finish

- [ ] 4.1 Run `npm test` and `npm run typecheck` in `pwa/`, and `npm test` in `firetv/`, all green
