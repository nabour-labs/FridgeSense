# camera-live-view Specification

## Purpose
TBD - created by archiving change wide-livestream-dialog. Update Purpose after archive.

## Requirements

### Requirement: Wide Livestream dialog
The "Livestream" dialog SHALL be wider than the app's other dialogs on screens `sm` and up: up to 768 px (`sm:max-w-3xl`) instead of 448 px (`max-w-md`), with the video filling its width at 16:9. This applies both to the live camera view and to the Mock video clip player. Other dialogs SHALL keep the 448 px width. On phones every dialog stays a full-width bottom sheet.

#### Scenario: Livestream dialog is wide
- **WHEN** the user opens the "Livestream" dialog
- **THEN** the dialog has the `sm:max-w-3xl` width and not `max-w-md`

#### Scenario: Mock video Livestream is wide
- **WHEN** Mock video is on and the user opens the "Livestream" dialog
- **THEN** the dialog has the `sm:max-w-3xl` width and not `max-w-md`

#### Scenario: Other dialogs keep their width
- **WHEN** any other sheet dialog opens
- **THEN** it has the `max-w-md` width

### Requirement: Open a live view
`POST /api/camera/live` SHALL accept an owner or user token and a JSON body `{"offer": "<SDP>"}`. It SHALL refuse a viewer token with 403 `{"error": "read-only"}` without calling Ring, because live video is never face-blurred. It SHALL send the offer unchanged to Ring's `POST /v1/devices/{device_id}/media/streaming/whep/sessions` for the account's first discovered camera, with `Content-Type: application/sdp`, and on a 2xx answer SHALL respond 200 `{"answer": "<Ring's SDP body>", "session_id": "<last path segment of Ring's Location header>", "max_seconds": 60}`. Nothing SHALL be stored.

#### Scenario: Live view opened
- **WHEN** an owner token calls `POST /api/camera/live` with `{"offer": "v=0\r\n..."}` and Ring answers 201 with body `v=0\r\nanswer` and `Location: /v1/devices/D1/media/streaming/whep/sessions/S123`
- **THEN** Ring received exactly the offer text with `Content-Type: application/sdp` and the account's bearer token, and the response is 200 `{"answer": "v=0\r\nanswer", "session_id": "S123", "max_seconds": 60}`

#### Scenario: User opens a live view
- **WHEN** a user token calls `POST /api/camera/live` with a valid offer and Ring answers 201
- **THEN** the response is 200 with the answer

#### Scenario: Viewer opens a live view
- **WHEN** a viewer token calls `POST /api/camera/live` with a valid offer
- **THEN** the response is 403 `{"error": "read-only"}` and Ring is not called

#### Scenario: Absolute Location
- **WHEN** Ring's `Location` header is `https://api.amazonvision.com/v1/devices/D1/media/streaming/whep/sessions/S9`
- **THEN** `session_id` is `S9`

#### Scenario: Bad offer
- **WHEN** the body is not JSON, has no `offer`, `offer` is not a string, is empty, does not start with `v=0`, or is longer than 20,000 characters
- **THEN** the response is 400 `{"error": "bad offer"}` and Ring is not called

#### Scenario: No camera
- **WHEN** the account has no discovered camera
- **THEN** the response is 409 `{"error": "no camera found"}` and Ring is not called

#### Scenario: Ring refuses the session
- **WHEN** Ring answers 400, 403, 404, 429 or 500, or answers 2xx without a `Location` header
- **THEN** the response is 502 `{"error": "camera unavailable"}`

#### Scenario: Ring unreachable or unlinked
- **WHEN** the Ring call times out, or Ring still answers 401 after a token refresh
- **THEN** the response is 502 `{"error": "camera unavailable"}`

#### Scenario: Not signed in
- **WHEN** `POST /api/camera/live` is called without a token
- **THEN** the response is 401 `{"error": "sign in"}` and Ring is not called

### Requirement: Close a live view
`DELETE /api/camera/live/{session_id}` SHALL accept an owner or user token, SHALL refuse a viewer token with 403 `{"error": "read-only"}` without calling Ring, and SHALL call Ring's `DELETE /v1/devices/{device_id}/media/streaming/whep/sessions/{session_id}` for the account's first camera. The Ring URL SHALL be built by the server; a `session_id` that is not 1–128 characters of letters, digits, `-`, `_`, `.` or `~` SHALL be refused without calling Ring.

#### Scenario: Live view closed
- **WHEN** a user token calls `DELETE /api/camera/live/S123` and Ring answers 200 or 204
- **THEN** Ring received `DELETE /v1/devices/{device_id}/media/streaming/whep/sessions/S123` and the response is 200 `{"ok": true}`

#### Scenario: Viewer refused a close
- **WHEN** a viewer token calls `DELETE /api/camera/live/S123`
- **THEN** the response is 403 `{"error": "read-only"}` and Ring is not called

#### Scenario: Session already gone
- **WHEN** Ring answers 404 to the delete
- **THEN** the response is 200 `{"ok": true}`

#### Scenario: Bad session id
- **WHEN** the session id is `..%2F..%2Fdevices` or 129 characters long
- **THEN** the response is 404 `{"error": "not found"}` and Ring is not called

#### Scenario: Ring fails the delete
- **WHEN** Ring answers 500 or the call times out
- **THEN** the response is 502 `{"error": "camera unavailable"}`

### Requirement: Livestream button on Activity
The Activity screen SHALL show a "Livestream" button to the owner and to users, and SHALL NOT show it to viewers. Tapping it SHALL open a dialog titled "Livestream" that asks the API for a live view and plays the camera's video muted and inline.

#### Scenario: Button for every role
- **WHEN** the Activity screen is shown to an owner, a user or a viewer
- **THEN** the owner and the user see a "Livestream" button, and the viewer sees none

#### Scenario: Live video plays
- **WHEN** the user taps "Livestream" and the API answers `{"answer": "...", "session_id": "S1", "max_seconds": 60}`
- **THEN** a dialog titled "Livestream" shows "Connecting…", sends the browser's offer to `POST /api/camera/live`, applies the answer, and once video arrives shows the video and "60 s left"

#### Scenario: Countdown
- **WHEN** the video has played for 15 s
- **THEN** the dialog shows "45 s left"

### Requirement: Livestream ends cleanly
The dialog SHALL close the peer connection and call `DELETE /api/camera/live/{session_id}` whenever it stops a stream: when the user closes the dialog, and when the time runs out. When the time runs out it SHALL show "Stream ended" and a "Watch again" button that starts a new live view.

#### Scenario: Close stops the stream
- **WHEN** video is playing for session `S1` and the user closes the dialog
- **THEN** the peer connection is closed and `DELETE /api/camera/live/S1` is called once

#### Scenario: Time runs out
- **WHEN** 60 s pass after the video started
- **THEN** the peer connection is closed, `DELETE /api/camera/live/S1` is called, and the dialog shows "Stream ended" and "Watch again"

#### Scenario: Watch again
- **WHEN** the user taps "Watch again"
- **THEN** a new offer is sent to `POST /api/camera/live` and the dialog shows "Connecting…"

#### Scenario: Closed while connecting
- **WHEN** the user closes the dialog before the API answers, and the API then answers with session `S2`
- **THEN** the peer connection is closed and `DELETE /api/camera/live/S2` is called

### Requirement: Livestream errors
The dialog SHALL show a message and a "Try again" button when the live view cannot start, and SHALL not raise the app's global error notice.

#### Scenario: Camera unavailable
- **WHEN** `POST /api/camera/live` answers 502 `{"error": "camera unavailable"}`
- **THEN** the dialog shows "The camera is not available right now." and "Try again", and no peer connection is left open

#### Scenario: No camera
- **WHEN** `POST /api/camera/live` answers 409 `{"error": "no camera found"}`
- **THEN** the dialog shows "No camera is linked yet."

#### Scenario: Video never arrives
- **WHEN** the answer is applied but no video frame has been decoded within 15 s (for example, the camera is unplugged)
- **THEN** the peer connection is closed, the session is deleted, and the dialog shows "The camera isn't sending video. Check that it's plugged in." and "Try again"

#### Scenario: Video track arrives before the answer is applied
- **WHEN** the browser fires the video track while the answer is being applied, and video frames are decoded within 15 s
- **THEN** the stream keeps playing past 15 s with its countdown and no error

#### Scenario: Connection fails
- **WHEN** the connection state becomes `failed`
- **THEN** the peer connection is closed, the session is deleted, and the dialog shows "Could not connect to the camera." and "Try again"

#### Scenario: Browser without WebRTC
- **WHEN** the browser has no `RTCPeerConnection`
- **THEN** the dialog shows "This browser can't play live video." and the API is not called
