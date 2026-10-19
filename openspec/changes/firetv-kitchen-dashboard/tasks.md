# Tasks

## 1. TV helpers (PWA)

- [x] 1.1 Write failing tests in `pwa/src/tv/tv.test.ts` for "Items by category", "More than fits" and "Empty fridge" (`fridgeRows`); run `npx vitest run src/tv` and see them fail on the missing module
- [x] 1.2 Implement `fridgeRows` in `pwa/src/tv/tv.ts` until they pass
- [x] 1.3 Write failing tests for "Newest five", "Change labels", "Analysis running" and "Quiet week" (`recentRows`), and "Today's count" and "One opening today" (`opensSummary`); confirm they fail
- [x] 1.4 Implement `recentRows` and `opensSummary` with `changeLabel`, `ago`, `todayCount` and `perDay` until `npx vitest run src/tv` passes

## 2. TV dashboard (PWA)

- [x] 2.1 Write failing tests in `pwa/src/tv/TvDashboard.test.tsx` for the three panels' content, "Inventory refresh" (fake timers), "Events fail, inventory loads", "Stills not shown", "No controls", "Only two endpoints" and "Back is left to the TV app"; confirm they fail
- [x] 2.2 Implement `TvDashboard.tsx` (two `useLoad` calls, three panels, `NoData` per panel, 1080p dark layout) until they pass
- [x] 2.3 Write failing tests in `pwa/src/App.test.tsx` for "Open at #tv", "Other hashes unchanged", "Switch to #tv while open", "Session expired on the TV", "Field focused" and "Enter signs in to the dashboard"; confirm they fail
- [x] 2.4 Route `#tv` to `TvDashboard` in `App.tsx` (no header, tabs or debug bar) until `npm test` in `pwa/` passes; then check it at 1920×1080 in the browser preview against the local dev server

## 3. Fire TV app (Vega OS)

- [x] 3.1 Install the Vega SDK and create `firetv/` from the basic React Native template; confirm the template builds (`vega build`) and runs on the Vega Virtual Device. Time-box to 2 hours; if it fails, log the friction and stop to ask about buying a stick (design.md decision 5, Fallback)
- [x] 3.2 Write failing tests in `firetv/test/site.test.ts` for "Loads #tv", "URL already ends with a slash or hash" and "Bad site URL"; confirm they fail
- [x] 3.3 Implement `tvUrl` in `firetv/src/site.ts`, plus `site.config.example.json` and a gitignored `site.config.json`, until they pass
- [x] 3.4 Write failing tests in `firetv/test/App.spec.tsx` for "WebView settings", "Offline TV" and "Try again" (WebView mocked); confirm they fail
- [x] 3.5 Implement `firetv/src/App.tsx` (WebView shell and failure screen) until they pass
- [x] 3.6 Write `firetv/test/secrets.test.ts` for "Source has no secrets", see it fail against a temporary file containing a fake `passcode: "x"`, remove that file and see it pass
- [x] 3.7 Make sure `firetv/package.json` has a `test` script that runs once and exits, and that `npm ci && npm test` works from a clean checkout (the `unit-tests` workflow runs it); if the Vega packages can't install on the CI runner, apply the fallback in design.md's Risks

## 4. Device check and docs

- [ ] 4.1 Build, sideload and run on the Vega Virtual Device (or a Fire TV): check "First launch", sign in with the viewer passcode, and watch the panels update after a real door opening; record this for the demo video
- [x] 4.2 Add a "Fire TV" section to README.md: set `site.config.json` from `SiteUrl`, build, run on the Vega Virtual Device or sideload to a Fire TV, sign in with the viewer passcode
- [x] 4.3 Add friction-log entries for any Vega SDK, Vega Virtual Device or Fire TV friction hit in 3.1–4.1

## 5. Finish

- [x] 5.1 Run the PWA suite (`npm test`, `npm run typecheck` in `pwa/`) and the firetv suite (`npm test` in `firetv/`) green, and the backend suite (`uv run pytest`, `uv run ruff check` in `backend/`) to confirm nothing else changed
