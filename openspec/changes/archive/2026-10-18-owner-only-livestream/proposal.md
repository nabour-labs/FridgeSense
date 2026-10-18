# Proposal

## Why

Live video is never face-blurred. Today the owner and anyone with the user passcode can open it (Activity → Livestream, Camera → Check decoder, and `POST /api/camera/live` directly). Only the owner should be able to watch the fridge live.

Tracks: Ring (Partner API live video), Open Source.

## What Changes

- **BREAKING (user role):** `POST /api/camera/live` and `DELETE /api/camera/live/{session_id}` become owner-only. A user token gets 403 `{"error": "admin only"}` and a viewer token keeps 403 `{"error": "read-only"}`. Ring is not called in either case.
- The "Livestream" button on Activity and the "Decoder" card on the Camera tab are shown to the owner only.
- Setup snapshots for a user (Reference images, Open/close detection, Fridge area) no longer open a live view. They take the newest recording's still from `POST /api/camera/snapshot`, which is already face-blurred and already open to users. The owner keeps getting snapshots from a live frame.

## Out of scope

- Blurring faces in live video.
- The Mock video Livestream and clip picker (dev server only, no Ring calls).
- Changing which roles can use `POST /api/camera/snapshot` or `POST /api/camera/frame`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `camera-live-view`: "Open a live view", "Close a live view" and "Livestream button on Activity" become owner-only.
- `camera-info`: "Browser decoder readout" becomes owner-only.
- `camera-snapshot`: "Snapshot from a live frame" applies to the owner only; adds "Users' snapshots from the newest recording".

## Impact

- Backend: `handlers/api.py` (the two live routes go from `write=True` to `owner=True`), `tests/test_api_live.py`.
- PWA: `screens/Activity.tsx`, `screens/Camera.tsx`, `App.tsx` (picks the snapshot source by role), and their tests.
- README: the Livestream paragraph.
- No infrastructure change.
- Depends on nothing in flight. `livestream-online-check` only adds requirements to `camera-live-view` and `camera-snapshot`, so the two changes don't conflict.
