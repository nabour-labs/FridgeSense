# Proposal

## Why

The app only shows the fridge through stills taken at door openings. Jayson wants to look into the fridge right now from the Activity screen ("is there still milk?"), and a live view is a strong Ring Partner API moment for the demo. Ring's API already offers live video over WebRTC (WHEP), so the app only needs a small proxy and a dialog.

Tracks: Ring (Partner API live video), AWS Builder (API Gateway, Lambda), Open Source.

## What Changes

- **API:** `POST /api/camera/live` takes the browser's WebRTC SDP offer, opens a WHEP session on the account's first camera through Ring (`POST /v1/devices/{id}/media/streaming/whep/sessions`, `Content-Type: application/sdp`), and returns the SDP answer, a session id and the session limit (60 s). The Ring token never leaves the backend.
- **API:** `DELETE /api/camera/live/{session_id}` ends that session at Ring. The backend builds the Ring URL from the device and the id; it never calls a URL the client sends.
- Both routes are open to **every signed-in role**, viewers included (opening a live view changes no data). Faces are **not** blurred in live video: this is an accepted trade-off.
- `RingClient` can send extra request headers (needed for `application/sdp`).
- **PWA:** a "Livestream" button at the top of the Activity screen. It opens a dialog (the existing `Sheet`) that connects and plays the camera's live video, shows the seconds left, and stops the stream when closed. When the 60 s run out it shows "Stream ended" and a "Watch again" button. Errors show a message and "Try again".
- **Mock API:** answers `POST /camera/live` with 502 `camera unavailable` so the dialog's error path can be checked in the browser preview without Ring.

## Out of scope

- Audio, two-way talk, recording or saving live video, snapshots from the live view.
- Face blurring of live video.
- Extending a session past Ring's 60 s limit without a user tap (no auto-reconnect).
- Choosing among several cameras (the first camera is used, as for snapshots).
- A TURN server: STUN only, as in Ring's sample.
- Live view on Fire TV or through the MCP server.

## Capabilities

### New Capabilities

- `camera-live-view`: opening and closing a live WebRTC view of the fridge camera through the app API, and the Livestream dialog in the PWA.

### Modified Capabilities

None. `Viewer tokens are read-only` lists its write routes explicitly, and the live routes are not write routes.

## Impact

- `backend/src/fridgesense/ring.py` (extra headers), new `backend/src/fridgesense/live.py`, `backend/src/fridgesense/handlers/api.py` (two routes)
- `pwa/src/api/client.ts`, `pwa/src/api/types.ts`, new `pwa/src/components/LiveStream.tsx`, `pwa/src/screens/Activity.tsx`
- `pwa/scripts/mock-api.ts`, README (one line on live view)
- No infra change: `/api/{proxy+}` already routes to the API Lambda. No new AWS cost beyond two Lambda calls per view; no S3 or Bedrock use.
