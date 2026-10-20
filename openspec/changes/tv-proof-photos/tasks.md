# Tasks

## 0. Base spec

- [ ] 0.1 Make sure `tv-dashboard-more` is archived (ask Jayson whether its task 3.1, the on-device check, is done or can be marked done), so `openspec/specs/tv-dashboard/spec.md` has "Nothing private or interactive on the TV dashboard"; verify with `openspec validate tv-proof-photos`

## 1. Picture helpers (`pwa/src/tv/tv.ts`)

- [x] 1.1 Write failing tests in `tv.test.ts` for "Proof under the labels", "At most three photos", "Change without proof", "Rejected change has no photo" and "No photos without changes" (including a collapsed no-change row) against `recentRows(...).proofs`; run `npx vitest run src/tv` in `pwa/` and see them fail
- [x] 1.2 Add `MAX_PROOFS = 3` and `proofs` to `RecentRow` in `recentRows` until 1.1 passes
- [x] 1.3 Write failing tests for "Newest opening's last still", "Newest opening has no stills" and "No stills at all" (`latestStill(events, timeZone)` → `{ src, caption } | null`, `America/Vancouver`), and for `stillBase` stripping the query string; confirm they fail
- [x] 1.4 Implement `latestStill` (reusing `clockTime`) and `stillBase` until `npx vitest run src/tv` passes

## 2. Photos on the dashboard (`pwa/src/tv/TvDashboard.tsx`)

- [x] 2.1 The spec changed "Stills not shown" into "Only opening pictures shown" and "No clips or video": rewrite that test in `TvDashboard.test.tsx` to match, and add failing tests for "Only opening pictures shown", "No clips or video", "Camera image not shown" and "No controls" with photos on screen, and "Only three endpoints" asserting no `camera/snapshot` call; confirm the new ones fail
- [x] 2.2 Write failing component tests for the proof thumbnails (`src` order, empty `alt`, none on "Checking…"/"No changes" rows) and for the header: "Newest opening's last still" (image with alt "Latest still from the fridge camera" and caption), "No stills at all" and "Events fail" (no image, camera line shown); confirm they fail
- [x] 2.3 Implement `TvPhoto` (64 px 4:3 thumbnails, `object-cover`, `decoding="async"`), the proof row under each row's labels, and the header still (16:9, ~120 px, caption, right side beside "Updated"), until 2.1 and 2.2 pass
- [x] 2.4 Write failing tests for "Broken link hidden" and "Header still fails" (`fireEvent.error` on the `img`), "Re-signed link kept" and "New picture replaces the old" (fake timers, events refresh at 30 s returning re-signed and newer links); confirm they fail
- [x] 2.5 Implement hide-on-error in `TvPhoto` and the `useStillSrc` hook (photos keyed by `stillBase`) until `npm test` in `pwa/` passes, with every existing TV scenario still green

## 3. Layout and docs

- [x] 3.1 Check the layout at 1920×1080 in the browser preview (`pwa-mock`, `#tv`): 5 Recent changes rows with photos fit without overflow, the header still doesn't push the panels down past the screen; take a screenshot. If rows overflow, apply design decision 3's fallback and note it in design.md
- [x] 3.2 Update the README's Fire TV section: the dashboard now shows proof photos and the latest still, face-blurred when the face-blur setting is on

## 4. Finish

- [x] 4.1 Run `npm test`, `npm run typecheck` and `npm run lint` (if present) in `pwa/`, and `npm test` in `firetv/`; all green
- [ ] 4.2 After the PWA deploy (ask first), relaunch the Fire TV app on the Vega Virtual Device and check that proof photos and the header still load and stay put across a 30 s refresh. Log any Vega WebView friction in `docs/friction-log.md`
