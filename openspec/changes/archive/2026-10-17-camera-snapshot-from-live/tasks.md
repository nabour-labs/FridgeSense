# Tasks

## 1. Backend: frame blur route

- [x] 1.1 Write failing tests in `backend/tests/test_api_camera_frame.py` (API handler, Rekognition Stubber, frozen `now`) for "Frame blurred and returned", "Face blurred in the frame", "Small frame kept at its size" and "Face detection unavailable". Run `uv run pytest tests/test_api_camera_frame.py` and confirm they fail with 404 `not found`.
- [x] 1.2 Add `POST /api/camera/frame` to `handlers/api.py` as a write route (decode, shrink, `FaceBlurrer.blur`, shrink, 502 on blur failure), reusing `camera.shrink`. Verify 1.1 passes.
- [x] 1.3 Write failing tests for "Missing image", "Not a JPEG" and "Too large" (assert face detection is not called). Run them red.
- [x] 1.4 Add the input checks (string, base64, ≤ 2,000,000 bytes, opens as JPEG → 400 `bad image`). Verify 1.3 passes.
- [x] 1.5 Write tests for "Viewer refused" and "No token"; they should pass from the existing write-route auth. If either is red, fix the route registration. Then `uv run pytest` and `uv run ruff check` green.

## 2. PWA: shared live connection

- [x] 2.1 Refactor: move the WebRTC setup out of `useLiveStream` into `openLive(api, createPeer)` in `pwa/src/components/LiveStream.tsx` (or a sibling module) returning the stream and a `stop()` that ends the session once. Keep every existing `LiveStream.test.tsx` test green with no test changes.
- [x] 2.2 Add `cameraFrame(image)` to `pwa/src/api/client.ts` with a client test for the request shape (`POST /api/camera/frame`, `{image}`). Run it red, then implement and see it green.

## 3. PWA: snapshot from a live frame

- [x] 3.1 Write failing tests in `pwa/src/camera/liveSnapshot.test.ts` (fake peer, fake video frame counter, stubbed canvas, mocked `api`, fake timers) for "Snapshot taken from the live view", "Live session ended before the frame is sent", "Unblurred frame never shown" (no `<video>` attached to `document`) and "Blurring fails" (no fallback request). Run them and confirm they fail because `liveSnapshot` does not exist.
- [x] 3.2 Implement `liveSnapshot(api, createPeer, signal?)`: open live, wait for 10 decoded frames, draw a ≤960 px JPEG, stop, `cameraFrame`. Verify 3.1 passes.
- [x] 3.3 Write failing tests for "Live route unavailable", "No frames in time", "Browser without WebRTC", "Fallback finds no footage" and "Screen closed while taking the snapshot". Run them red.
- [x] 3.4 Add the fallback to `api.cameraSnapshot()` and abort handling. Verify 3.3 passes.

## 4. PWA: wiring and Mock video

- [x] 4.1 Write failing tests: with Mock video off, "Camera snapshot" in Reference images, "Add" in Open/close detection and "Set area" in Fridge area request `POST /api/camera/live` (the mock-camera-video "Switch off" scenario); with it on, "Reference image from a clip" requests none of `/api/camera/live`, `/api/camera/frame`, `/api/camera/snapshot`. Run them red.
- [x] 4.2 Wire `liveSnapshot` in place of `cameraSnapshot` where the app builds its `api` (beside `withSnapshot`), so Mock video still overrides it. Pass the sheet's abort signal from the three screens. Verify 4.1 passes and the existing "Door reference from a clip" and "Cancel" tests stay green.

## 5. Mock API, docs, checks

- [x] 5.1 Answer `POST /api/camera/frame` in `pwa/scripts/mock-api.ts` by echoing the image with the current time; check it in the browser preview with Mock video off (live fails in the mock, so the fallback path shows).
- [x] 5.2 Update the README setup step that says to walk past the camera: snapshots now come from the live view, with the Ring still as a fallback.
- [x] 5.3 Add a friction-log entry if the Ring live view or Rekognition caused friction while building this; add nothing otherwise.
- [x] 5.4 Run the full suites and linters green: `cd backend && uv run pytest && uv run ruff check && uv run ruff format --check`, and `cd pwa && npm test && npm run typecheck`. Report the commands and results.
