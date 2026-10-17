# Proposal

## Why

With the camera unplugged, Ring still accepts a live session and reports the camera online, but sends no video. The Livestream dialog then shows a black picture with a countdown, and setup snapshots silently fall back to an old recording. Separately, the "no video within 15 s" timer starts after the track has already arrived (browsers fire `track` during `setRemoteDescription`), so it cuts off working streams at 15 s with "Could not connect to the camera."

Tracks: Ring (Partner API live video), Open Source.

## What Changes

- The live view's 15 s check waits for decoded video frames, not for the video track. If none arrive, the Livestream dialog shows "The camera isn't sending video. Check that it's plugged in." with "Try again", and ends the session.
- A connection that reaches `failed` still shows "Could not connect to the camera."
- A setup snapshot whose live view connects but gets no frames in 15 s shows the same "camera isn't sending video" message instead of falling back to the newest recording. Other live-view failures (no WebRTC, live route error, failed connection) still fall back to the Ring still.
- The stream is no longer cut off at 15 s while video plays.

## Out of scope

- Reading the camera's power state from Ring (its `online` status lags behind an unplugged camera).
- Changing the 15 s limit or the 60 s session length.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `camera-live-view`: "Livestream errors" — the no-video case is judged by decoded frames and gets its own message.
- `camera-snapshot` (still a delta in `camera-snapshot-from-live`, edited there): "Fall back to the Ring still" no longer covers the no-frames case.

## Impact

`pwa/src/components/LiveStream.tsx`, `pwa/src/camera/liveSnapshot.ts`, the three setup screens' error handling, and their tests. No backend change.
