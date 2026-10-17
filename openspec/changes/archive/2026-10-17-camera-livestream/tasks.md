# Tasks

## 1. Backend: Ring WHEP calls

- [x] 1.1 Write failing tests in `backend/tests/test_live.py` (respx) for `RingClient` extra headers (caller `Content-Type` sent, `Authorization` not overridable) and for `live.start` / `live.stop`: "Live view opened", "Absolute Location", "Ring refuses the session", "Ring unreachable or unlinked", "Live view closed", "Session already gone", "Ring fails the delete". Run `uv run pytest tests/test_live.py` and confirm they fail because the headers merge and `fridgesense.live` do not exist.
- [x] 1.2 Merge caller headers in `RingClient` and add `fridgesense/live.py` (`start`, `stop`, `LiveFailed`, session id from `Location`). Verify 1.1 passes and all backend tests stay green.

## 2. Backend: API routes

- [x] 2.1 Write failing tests in `backend/tests/test_api_live.py` for "Live view opened", "Viewer opens a live view", "Bad offer", "No camera", "Ring refuses the session", "Not signed in", "Live view closed" (viewer token), "Bad session id" and "Ring fails the delete" through `api.handler`. Run them and confirm they fail with 404 `not found`.
- [x] 2.2 Add `POST /api/camera/live` and `DELETE /api/camera/live/{session_id}` to `handlers/api.py` (not `write`, `with_device`, offer and id validation, 502 mapping with `log_event("live_failed")`). Verify 2.1 passes, then `uv run pytest` and `uv run ruff check` green.

## 3. PWA: Livestream dialog

- [x] 3.1 Add `startLive(offer)` and `stopLive(sessionId)` to `pwa/src/api/client.ts` with a `LiveSession` type, plus a client test for the request shapes. Run it red, then implement and see it green.
- [x] 3.2 Write failing tests in `pwa/src/components/LiveStream.test.tsx` (fake peer, stubbed client, fake timers) for "Live video plays", "Countdown", "Close stops the stream", "Time runs out", "Watch again", "Closed while connecting", "Camera unavailable", "No camera", "Video never arrives" and "Browser without WebRTC". Run them and confirm they fail because `LiveStream` does not exist.
- [x] 3.3 Implement `useLiveStream` and the `LiveStream` dialog on `Sheet`. Verify 3.2 passes.

## 4. PWA: Activity button

- [x] 4.1 Write failing tests in `pwa/src/screens/Activity.test.tsx` for "Button for every role" (owner and viewer) and that tapping it opens the "Livestream" dialog. Run them red.
- [x] 4.2 Add the "Livestream" button (lucide `Video` icon) beside the day picker in `Activity.tsx`. Verify 4.1 passes and `npm test` is green.

## 5. Mock, docs, checks

- [x] 5.1 Make `pwa/scripts/mock-api.ts` answer `POST /camera/live` with 502 `{"error": "camera unavailable"}` and `DELETE /camera/live/{id}` with 200; add a README line on live view (60 s limit, faces not blurred, open to viewers).
- [x] 5.2 Run `uv run pytest`, `uv run ruff check` in `backend/` and `npm test`, `npm run build` in `pwa/`, all green. In the browser preview with the mock API, open the dialog from Activity and check the error state and "Try again"; screenshot it.
- [ ] 5.3 After Jayson approves a deploy, open one real live view: video plays, closing deletes the session, no `motion_detected` webhook follows. Add friction-log entries for anything surprising (e.g. audio m-line rejected).
