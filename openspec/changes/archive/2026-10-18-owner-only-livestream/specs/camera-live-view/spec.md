## MODIFIED Requirements

### Requirement: Open a live view
`POST /api/camera/live` SHALL accept only an owner token and a JSON body `{"offer": "<SDP>"}`. It SHALL refuse a user token with 403 `{"error": "admin only"}` and a viewer token with 403 `{"error": "read-only"}`, without calling Ring, because live video is never face-blurred. It SHALL send the offer unchanged to Ring's `POST /v1/devices/{device_id}/media/streaming/whep/sessions` for the account's first discovered camera, with `Content-Type: application/sdp`, and on a 2xx answer SHALL respond 200 `{"answer": "<Ring's SDP body>", "session_id": "<last path segment of Ring's Location header>", "max_seconds": 60}`. Nothing SHALL be stored.

#### Scenario: Live view opened
- **WHEN** an owner token calls `POST /api/camera/live` with `{"offer": "v=0\r\n..."}` and Ring answers 201 with body `v=0\r\nanswer` and `Location: /v1/devices/D1/media/streaming/whep/sessions/S123`
- **THEN** Ring received exactly the offer text with `Content-Type: application/sdp` and the account's bearer token, and the response is 200 `{"answer": "v=0\r\nanswer", "session_id": "S123", "max_seconds": 60}`

#### Scenario: User opens a live view
- **WHEN** a user token calls `POST /api/camera/live` with a valid offer
- **THEN** the response is 403 `{"error": "admin only"}` and Ring is not called

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
`DELETE /api/camera/live/{session_id}` SHALL accept only an owner token. It SHALL refuse a user token with 403 `{"error": "admin only"}` and a viewer token with 403 `{"error": "read-only"}`, without calling Ring. It SHALL call Ring's `DELETE /v1/devices/{device_id}/media/streaming/whep/sessions/{session_id}` for the account's first camera. The Ring URL SHALL be built by the server; a `session_id` that is not 1–128 characters of letters, digits, `-`, `_`, `.` or `~` SHALL be refused without calling Ring.

#### Scenario: Live view closed
- **WHEN** an owner token calls `DELETE /api/camera/live/S123` and Ring answers 200 or 204
- **THEN** Ring received `DELETE /v1/devices/{device_id}/media/streaming/whep/sessions/S123` and the response is 200 `{"ok": true}`

#### Scenario: User refused a close
- **WHEN** a user token calls `DELETE /api/camera/live/S123`
- **THEN** the response is 403 `{"error": "admin only"}` and Ring is not called

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
The Activity screen SHALL show a "Livestream" button to the owner only, and SHALL NOT show it to users or viewers. Tapping it SHALL open a dialog titled "Livestream" that asks the API for a live view and plays the camera's video muted and inline.

#### Scenario: Button for every role
- **WHEN** the Activity screen is shown to an owner, a user or a viewer
- **THEN** the owner sees a "Livestream" button, and the user and the viewer see none

#### Scenario: Live video plays
- **WHEN** the owner taps "Livestream" and the API answers `{"answer": "...", "session_id": "S1", "max_seconds": 60}`
- **THEN** a dialog titled "Livestream" shows "Connecting…", sends the browser's offer to `POST /api/camera/live`, applies the answer, and once video arrives shows the video and "60 s left"

#### Scenario: Countdown
- **WHEN** the video has played for 15 s
- **THEN** the dialog shows "45 s left"
