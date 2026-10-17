# Proposal

## Why

Setup snapshots (reference images, door references, fridge area) ask Ring for a still at "now − 3 s". The camera only records when something moves, so the request almost always fails with "No recent footage", and the newest-motion fallback shows the fridge as it was at the last motion, not now. A live view always has a current picture, and the app already opens one for the Livestream dialog.

Tracks: Ring (Partner API live video), AWS Builder (Lambda, Rekognition), Open Source.

## What Changes

- **PWA:** every setup snapshot first takes one frame from a short live view: open a session (`POST /api/camera/live`), wait until the video shows real frames, draw one to a canvas as a JPEG, end the session (`DELETE /api/camera/live/{id}`), and send the frame to the new blur route. The unblurred frame is never shown, stored or kept after the request.
- **PWA:** if the live view fails (no WebRTC, no connection, no frame in time, 502 from the live route), the snapshot falls back to `POST /api/camera/snapshot`, which keeps its newest-motion-event fallback. The screens keep their current messages ("No recent footage…", "Try again").
- **API:** new owner-only route `POST /api/camera/frame` with `{"image": "<base64 JPEG>"}`. It blurs every face the same way door stills are blurred, scales the frame down to at most 960 px wide and 300,000 bytes, stores nothing, and answers 200 `{"image", "captured_at"}` (the shape `POST /api/camera/snapshot` already returns). A missing, non-JPEG or oversized image gets 400 `{"error": "bad image"}`; failed face detection gets 502 and no image.
- While "Mock video" is on, snapshots still come from the clip picker; no live view is opened.
- **Mock API:** answers `POST /api/camera/frame` by echoing the image, so the screens work in the browser preview.

## Out of scope

- Blurring faces in the Livestream dialog itself (still an accepted trade-off).
- Picking which frame to use, or showing the live video before the snapshot is taken.
- Removing `POST /api/camera/snapshot` or its newest-motion fallback.
- Snapshots on Fire TV or through the MCP server.
- A TURN server (STUN only, as for the Livestream dialog).

## Capabilities

### New Capabilities

- `camera-snapshot`: how the app gets one current, face-blurred picture from the fridge camera for setup screens: the live-frame capture in the PWA, its fallback to the Ring still, and the `POST /api/camera/frame` blur route.

### Modified Capabilities

- `mock-camera-video`: "Snapshots come from a clip while the switch is on" says that with the switch off a snapshot calls `POST /api/camera/snapshot`; it now takes a live frame first.

## Impact

- New `backend/src/fridgesense` frame handling (reuses `camera.shrink` and `FaceBlurrer`), `backend/src/fridgesense/handlers/api.py` (one route), backend tests.
- `pwa/src/api/client.ts` (`cameraFrame`), a new snapshot helper that reuses the WebRTC setup in `pwa/src/components/LiveStream.tsx`, and the three screens that call `api.cameraSnapshot()` (`ReferenceImages.tsx`, `DoorDetection.tsx`, `FridgeArea.tsx`), plus the mock API.
- Each snapshot opens a Ring live session for a few seconds and makes one Rekognition `DetectFaces` call, as today.
- The `door-calibration` snapshot requirement (still a delta in `door-zone-setup`) is unchanged; this change adds routes beside it.
