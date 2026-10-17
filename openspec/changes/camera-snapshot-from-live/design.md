# Design

## Context

See proposal.md (Why). Today the three setup screens call `api.cameraSnapshot()` (`pwa/src/api/client.ts`), and the debug layer swaps that one method for the clip picker (`pwa/src/debug/debug.ts`, `withSnapshot`). The Livestream dialog (`pwa/src/components/LiveStream.tsx`) already knows how to open a WHEP session through `POST /api/camera/live`, wait for ICE, and end the session with `DELETE /api/camera/live/{id}`. On the backend, `camera.snapshot` already blurs (`FaceBlurrer`) and shrinks (`camera.shrink`) Ring stills.

## Goals / Non-Goals

**Goals:** one snapshot function the screens call, unchanged screen code apart from that call; the backend stays the only place faces are blurred; the live session lasts only as long as needed.

**Non-Goals:** sharing a live session between snapshots; any change to the Livestream dialog's behavior.

## Decisions

1. **Swap the implementation behind `api.cameraSnapshot`, not the screens.** A wrapper (`liveSnapshot(api, createPeer)`) returns the same `Snapshot` shape and throws the same `ApiError`s, so `ReferenceImages`, `DoorDetection` and `FridgeArea` and their messages stay as they are. The app wires it in where `withSnapshot` already swaps the method for Mock video, so Mock video still wins. *Alternative:* a new hook in each screen. Rejected: three copies of the same change.

2. **Pull the WebRTC setup out of `useLiveStream` into a plain function** (`openLive(api, createPeer)` → `{stream, stop}`), used by both the dialog hook and the snapshot. *Alternative:* render a hidden `<LiveStream>`. Rejected: it renders video and a sheet; the snapshot must show nothing unblurred.

3. **Frame readiness: 10 decoded frames, 15 s budget.** The first frames after a WHEP connect are often grey until a keyframe arrives. The frame is read from a detached `<video>` (never in the DOM) using `requestVideoFrameCallback` when present, otherwise `getVideoPlaybackQuality().totalVideoFrames` checked on a timer. 15 s matches the dialog's `TRACK_WAIT_MS`.

4. **Scale in the browser to ≤960 px, JPEG quality 0.9.** That keeps the upload near 100–300 KB, well under API Gateway and Lambda limits, and matches what the backend returns anyway. The backend still runs `shrink` on input and output, so it does not trust the client's size.

5. **End the session before uploading.** The frame is in memory, so the 60 s Ring session is closed as soon as the canvas is drawn. This also keeps live sessions from overlapping if the owner taps "New snapshot" again.

6. **New route `POST /api/camera/frame` as a write route.** It reuses the snapshot handler's pieces: decode → size check (2,000,000 bytes) → Pillow open (must be JPEG) → `shrink` → `FaceBlurrer.blur` → `shrink`. It needs no device, so it does not use `@with_device`; it still needs a linked account like the snapshot route. Fail closed: no blur result means 502 and no image. *Alternative:* blur in the browser. Rejected: there is no face model in the PWA, and the backend blurs every other image.

7. **Fallback lives in the wrapper.** Any failure before the frame is drawn (no WebRTC, live route error, connection failed, frame timeout) calls the original `api.cameraSnapshot()` once. Errors from `POST /api/camera/frame` are *not* a reason to fall back: the frame was fine and the blur failed, so a Ring still would fail the same way. A 401 from any call goes to `report` as today.

8. **Cancel by `AbortSignal`.** Screens already unmount the sheet on close; the wrapper takes an optional signal, ends the session, and resolves nothing when aborted.

## Risks / Trade-offs

- [The unblurred frame exists in browser memory and in one HTTPS request] → it is never rendered or stored, and the request goes only to the app's own API, as Mock video frames already do.
- [Ring live sessions take a few seconds to start, slower than a still] → the screens already show a loading state; the fallback covers a camera that will not stream.
- [Rekognition is charged per frame, as for the Ring still] → same one call per snapshot as today; the route is owner-only and covered by the default rate limit.
- [Safari has no `decoderImplementation` and older Safari has no `requestVideoFrameCallback`] → the playback-quality fallback handles it.

## Migration Plan

Backend first (the new route is unused until the PWA ships), then the PWA. Rollback: redeploy the previous PWA; `POST /api/camera/snapshot` is untouched.

## Test strategy

- **Backend unit (pytest):** the frame route through the API handler with a stubbed Rekognition client (botocore Stubber), JPEG fixtures from `tests/conftest.py` (`color_jpeg`, `checkerboard_jpeg`) and `rekognition/detect_faces_one.json`. One test per scenario in `specs/camera-snapshot` for the route: success size and `captured_at` (frozen `now`), face blur, small frame, detection failure, each bad-image case, viewer 403, no token 401, and no S3 or table writes.
- **PWA unit (Vitest):** `liveSnapshot` with a fake `RTCPeerConnection` (as in `LiveStream.test.tsx`), a fake video that reports decoded frames, a stubbed canvas, and a mocked `api`. Covers the call order (live → delete → frame), each fallback path, the frame timeout with fake timers, abort, and that no `<video>` is attached to the document.
- **Screen tests:** the existing Reference images, Open/close detection and Fridge area snapshot tests keep passing with `cameraSnapshot` mocked; one new test per screen that the live-frame path is wired in when Mock video is off.
- **Mock API:** `POST /api/camera/frame` echoes the image; checked by its existing contract test style.
- No test calls Ring, Rekognition or AWS.
