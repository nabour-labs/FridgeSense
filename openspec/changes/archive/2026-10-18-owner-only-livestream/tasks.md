# Tasks

## 0. Branch

- [x] 0.1 Branch `feat/owner-only-livestream` off `local`.

## 1. Live routes owner-only (backend)

- [x] 1.1 In `backend/tests/test_api_live.py`:
  - Write failing tests for "User opens a live view" (now refused) and "User refused a close".
  - Switch "Live view closed" to an owner token.
  - Keep "Viewer opens a live view", "Viewer refused a close" and every other scenario of "Open a live view" and "Close a live view".
  - Run them red.
- [x] 1.2 Change `POST /api/camera/live` and `DELETE /api/camera/live/{session_id}` to `owner=True` in `handlers/api.py`. Verify that 1.1 and the whole file pass.

## 2. Owner-only Livestream and Decoder (PWA)

- [x] 2.1 Write failing tests: "Button for every role" in `Activity.test.tsx` (the user sees no Livestream button), and "No Decoder card for a user" in `Camera.test.tsx`. Keep "Live video plays", "Countdown", "Decoder values after a check", "Before any check", "No video played" and "No Decoder card for a viewer" on the owner role. Run them red.
- [x] 2.2 Gate the Livestream button and `<Decoder>` with `isAdmin(role)`, and update the comment above the button. Verify that 2.1 passes.

## 3. Users' snapshots from the newest recording (PWA)

- [x] 3.1 Write failing tests for "User takes a reference snapshot", "User snapshot with no recent footage" and "User snapshot fails": a user role, with `startLive`, `stopLive` and `cameraFrame` spies that are never called. Re-run the "Snapshot from a live frame" tests on the owner role. Run them red.
- [x] 3.2 In `App.tsx`, choose the snapshot source by role: `liveSnapshot` for the owner, `api.cameraSnapshot()` otherwise. Mock video is unchanged. Verify that 3.1 passes.

## 4. Docs and checks

- [x] 4.1 Update the README Livestream paragraph and the setup snapshot step to say that live video and live snapshots are the owner's only.
- [x] 4.2 Run `cd backend && uv run pytest && uv run ruff check` and `cd pwa && npm test && npm run typecheck`, all green, and report the result.
