# Tasks

## 1. Live view: no-video detection

- [x] 1.1 Write failing tests in `pwa/src/components/LiveStream.test.tsx` for "Video never arrives" (new message), "Video track arrives before the answer is applied" and "Connection fails"; give the fake peer a `framesDecoded` counter in `getStats`. Run them red.
- [x] 1.2 In `openLive`, replace the track timer with a 15 s `framesDecoded` check from `getStats`, reporting `NO_VIDEO`. Verify 1.1 and all LiveStream tests pass.

## 2. Snapshot: camera not sending video

- [x] 2.1 Write failing tests in `pwa/src/camera/liveSnapshot.test.ts` for "No frames in time" (rejects `NoVideo`, no fallback) and "Connection fails before any frame" (fallback), and a screen test that `NoVideo` shows "The camera isn't sending video. Check that it's plugged in." with "Try again". Run them red.
- [x] 2.2 Add `NoVideo` to `liveSnapshot` and handle it in `ReferenceImages`, `DoorDetection` and `FridgeArea`. Verify 2.1 passes.

## 3. Checks

- [x] 3.1 Run `cd pwa && npm test && npm run typecheck` green and report the result.
