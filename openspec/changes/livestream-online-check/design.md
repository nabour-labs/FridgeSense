# Design

## Context

`useLiveStream` in `pwa/src/components/LiveStream.tsx` calls `openLive` on start. `GET /api/camera` (`api.camera()`) returns Ring's device status with `online: true | false | null` and takes one Ring call (~0.5 s).

## Decisions

1. **One helper, `cameraOffline(api)`, used in two places:** `useLiveStream.start` for the dialog, and `liveSnapshot` before the live frame. Not inside `openLive`, which stays a plain connection helper. `liveSnapshot` throws `CameraOffline` (like `NoVideo`), and the three screens show its message. Mock video swaps out `cameraSnapshot` entirely, so it never reaches the check.
2. **Only `online: false` blocks.** A null status, a 502 or a network error starts the live view anyway: blocking on an unknown status would hide a working camera. A 401 still goes to `report` (sign in again), as for the live route.
3. **"Connecting…" until the `<video>` fires `playing`.** The countdown keeps starting at the track, as today, so the session limit stays accurate.
4. A start that is superseded (dialog closed, or "Try again" tapped again) while the check is pending is dropped: a run counter in the hook ignores stale answers.

## Risks / Trade-offs

- [Ring keeps an unplugged camera "online" for a while] → the existing 15 s no-video message covers that window.
- [One extra Ring call before each live view] → about 0.5 s more under "Connecting…".

## Test strategy

Vitest only. `LiveStream.test.tsx` and `liveSnapshot.test.ts`, with the fake peer and `fakeApi` (`camera` mocked per test, fake timers). One test per scenario, plus screen tests for Reference images and Open/close detection showing the offline message. Existing tests get `camera` resolving `online: true`. `fireEvent.playing` on the video stands in for playback. No Ring or AWS calls.
