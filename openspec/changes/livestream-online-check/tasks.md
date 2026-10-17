# Tasks

## 1. Online check

- [x] 1.1 Write failing tests in `pwa/src/components/LiveStream.test.tsx` for "Camera offline", "Camera online", "Status unknown" (null, 502, network error), "Try again after offline" and "Closed during the check". Default `camera` in the test helper to `online: true`. Run them red.
- [x] 1.2 In `useLiveStream.start`, ask `api.camera()` first; on `online: false` show the offline message without a peer; otherwise call `openLive`. Ignore stale starts. Verify 1.1 and all LiveStream tests pass.

## 2. No black picture

- [x] 2.1 Write failing tests for "Track arrived, video not playing yet" and "Video plays". Run them red.
- [x] 2.2 Track a `playing` flag from the `<video>`'s `playing` event and keep "Connecting…" over the video until it is set. Verify 2.1 passes.

## 3. Online check before a snapshot

- [x] 3.1 Write failing tests in `pwa/src/camera/liveSnapshot.test.ts` for "Camera online", "Status unknown" and an offline check that rejects `CameraOffline` with no live, frame or snapshot request; and screen tests for "Reference image while the camera is offline" (ReferenceImages) and "Door reference while the camera is offline" (DoorDetection). Confirm "Mock video on" is covered by `DebugBar.test.tsx` asserting `camera` is not called. Run them red.
- [x] 3.2 Add `CameraOffline` and the check to `liveSnapshot`, and show its message in `ReferenceImages`, `DoorDetection` and `FridgeArea`. Verify 3.1 passes.

## 4. Checks

- [x] 4.1 Run `cd pwa && npm test && npm run typecheck` green and report the result.
