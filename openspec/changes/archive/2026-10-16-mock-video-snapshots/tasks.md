# Tasks

## 1. Dev-server clip routes

- [x] 1.1 Write failing tests in `pwa/scripts/dev-videos.test.ts` (node environment, temp folder with `a.mp4` 10 B, `b.mp4` 20 B, `notes.txt`): "Listing", "Missing folder", "Range request", "Whole file", "Path escape refused", "Unknown clip", and `upload` true only with `FRIDGESENSE_URL`. Run `npm test -- dev-videos` and see them fail because the module is missing.
- [x] 1.2 Implement `pwa/scripts/dev-videos.ts` (`devVideos({dir})` plugin, `apply: "serve"`, folder from `FRIDGESENSE_VIDEOS` or `<repo>/tmp`) and register it in `vite.config.ts`. Verify the 1.1 tests pass and that `npm test` passes.

## 2. Switch and clip picker

- [x] 2.1 Write failing tests in `pwa/src/debug/mockVideo.test.ts` for "Turned on, then reload" (stored round trip) and "Storage blocked" (throwing storage starts off, can be toggled, no throw). Implement the stored-switch helpers and verify.
- [x] 2.2 Write failing tests in `pwa/src/debug/ClipPicker.test.tsx` (stubbed `fetch`, injected frame grabber) for "Clips listed", "Frame size" (960×540 from 2560×1440), "No clips", "Clip won't load", "Deployed backend notice", "Mock API has no notice" and "Cancel" (resolves as cancelled).
- [x] 2.3 Implement `pwa/src/debug/ClipPicker.tsx` (`Sheet`, clip `Select`, `<video>` with range scrubber, "Use this frame", "Cancel") and the canvas frame grabber using `fitWithin(…, 960)`. Verify the 2.2 tests pass.

## 3. Debug mode and the snapshot swap

- [x] 3.1 Write failing tests in `pwa/src/debug/DebugBar.test.tsx` and `App.test.tsx` with `vi.stubEnv("DEV", …)`:
  - "Dev server" (the bar and an unchecked switch are shown).
  - "Production build" (no bar, no switch, `/__dev/videos` never fetched).
  - "Reference image from a clip" (fake API `cameraSnapshot` not called, the form shows the frame).
  - "Door reference from a clip" (the picker opens on "Add").
  - "Switch off" (`cameraSnapshot` called once, no picker).
  - "Cancel" (no error text, no request, nothing passed to `report`).
- [x] 3.2 Implement `isDebug()`, `PickCancelled`, the `withSnapshot(api, fn)` wrapper, the Debug bar, the picker host in `App.tsx`, and `report` ignoring `PickCancelled`. Verify the 3.1 tests and all existing `App`, `Config`, `DoorDetection`, `FridgeArea` and `ReferenceImages` tests pass unchanged.

## 4. Livestream from a clip

- [x] 4.1 Write failing tests in `pwa/src/debug/ClipLive.test.tsx` and `pwa/src/components/LiveStream.test.tsx` for "Livestream from a clip", "Change clip", "Livestream with no clips" and "Livestream switch off" (with a `DebugContext` provider; `fetch` stubbed; fake API's `startLive` must not be called when on).
- [x] 4.2 Implement `DebugContext`, `ClipLive`, and the `LiveStream` switch (existing body moved to `RealLiveStream`), with the provider in `App.tsx`. Verify the 4.1 tests and all existing `LiveStream` and `Activity` tests pass unchanged.

## 5. Docs and checks

- [x] 5.1 Add a short "Mock video (localhost)" note to the README covering:
  - the switch (snapshots and Livestream);
  - `FRIDGESENSE_VIDEOS`;
  - that frames are unblurred and get uploaded when proxying to a deployed backend.
  - Verify the note matches the commands as written.
- [x] 5.2 Run `npm run build` in `pwa/` and confirm `grep -r "__dev/videos" pwa/dist` finds nothing.
- [x] 5.3 In the browser preview (`pwa-mock`) with the real `tmp/` clips:
  - take a frame in Reference images, Open/close detection and Fridge area;
  - scrub a 25 MB clip;
  - open Livestream, check that it plays and loops, and switch clips;
  - check the bar and picker at 375 px in light and dark.
- [x] 5.4 Run the full checks green and report the commands and results: `cd pwa && npm test && npm run typecheck && npm run build`.
