# camera-snapshot Specification

## Purpose
Gives the setup screens one current, face-blurred picture of the fridge on demand: a frame taken from a short live view and blurred by the backend, with the Ring still as a fallback.

## Requirements

### Requirement: Blur a live frame
`POST /api/camera/frame` SHALL take `{"image": "<base64 JPEG>"}` and scale it down to at most 960 px wide, keeping its aspect ratio. While face blurring is on (the default, see `face-blur-setting`), it SHALL blur every face in the frame as door-event stills are blurred. While face blurring is off, it SHALL NOT call face detection. It SHALL answer 200 `{"image": "<base64 JPEG>", "captured_at": "<ISO 8601 UTC>"}`, where `captured_at` is the time the request was handled. The returned image SHALL be at most 300,000 bytes. Neither the frame nor the result SHALL be stored.

#### Scenario: Frame blurred and returned
- **WHEN** the owner sends a 1920×1080 JPEG with no faces at 2026-10-15T19:20:10Z
- **THEN** the response is 200, `image` decodes to a 960×540 JPEG of at most 300,000 bytes, `captured_at = "2026-10-15T19:20:10.000Z"`, and nothing is written to the table or S3

#### Scenario: Face blurred in the frame
- **WHEN** face blurring is on and face detection reports a face at `(0.40, 0.20, 0.20, 0.30)` in the frame
- **THEN** the returned image is blurred inside that face's enlarged box

#### Scenario: Frame while blurring is off
- **WHEN** face blurring is off and the owner sends a 1920×1080 JPEG
- **THEN** face detection is not called and the response is 200 with a 960×540 image

#### Scenario: Small frame kept at its size
- **WHEN** the owner sends a 640×360 JPEG
- **THEN** the returned image is 640×360

#### Scenario: Face detection unavailable
- **WHEN** face blurring is on and face detection fails
- **THEN** the response is 502 `{"error": "camera unavailable"}` and no image is returned

### Requirement: Frame input is checked
The frame route SHALL answer 400 `{"error": "bad image"}`, without calling face detection, when `image` is missing or not a string, is not valid base64, decodes to more than 2,000,000 bytes, or is not a JPEG that can be opened.

#### Scenario: Missing image
- **WHEN** the body is `{}` or not JSON
- **THEN** the response is 400 `{"error": "bad image"}` and face detection is not called

#### Scenario: Not a JPEG
- **WHEN** `image` is the base64 of a PNG, or of the text `hello`
- **THEN** the response is 400 `{"error": "bad image"}`

#### Scenario: Too large
- **WHEN** `image` decodes to 2,000,001 bytes
- **THEN** the response is 400 `{"error": "bad image"}` and face detection is not called

### Requirement: Frame route is owner-only
The frame route SHALL follow the existing auth rules for write routes: it needs a valid token, a viewer token SHALL get 403 `{"error": "read-only"}`, and it needs a linked account (otherwise 409).

#### Scenario: Viewer refused
- **WHEN** a viewer token calls `POST /api/camera/frame`
- **THEN** the response is 403 `{"error": "read-only"}` and face detection is not called

#### Scenario: No token
- **WHEN** the route is called without a token
- **THEN** the response is 401

### Requirement: Snapshot from a live frame
When the owner is signed in, a setup screen asks for a camera snapshot ("Camera snapshot" in Reference images, the add sheet and "New snapshot" in Open/close detection, the set-area sheet and "New snapshot" in Fridge area) and "Mock video" is off, the app SHALL open a live view (`POST /api/camera/live`), wait until at least 10 video frames have been decoded, draw the current frame as a JPEG at most 960 px wide, end the live session (`DELETE /api/camera/live/{session_id}`), and send the frame to `POST /api/camera/frame`. The screen SHALL show only the image that route returns.

#### Scenario: Snapshot taken from the live view
- **WHEN** the owner taps "Camera snapshot", the live view connects and plays 10 frames of 1920×1080 video, and the frame route answers 200
- **THEN** `POST /api/camera/live` is requested once, `POST /api/camera/frame` is requested once with a 960×540 JPEG, `DELETE /api/camera/live/{session_id}` is requested once, `POST /api/camera/snapshot` is not requested, and the reference form shows the returned image

#### Scenario: Live session ended before the frame is sent
- **WHEN** the frame has been drawn
- **THEN** `DELETE /api/camera/live/{session_id}` is requested before `POST /api/camera/frame`

#### Scenario: Unblurred frame never shown
- **WHEN** the live view is playing and the frame route has not answered yet
- **THEN** no live video and no unblurred frame are rendered on the screen, only the screen's loading state

#### Scenario: Blurring fails
- **WHEN** the frame route answers 502
- **THEN** the screen shows the same message it shows today when `POST /api/camera/snapshot` answers 502 (for Reference images, "The camera can't be reached right now."), no image is shown, and `POST /api/camera/snapshot` is not requested

### Requirement: Fall back to the Ring still
If the live view cannot give a frame, the app SHALL request `POST /api/camera/snapshot` once instead and handle its answer as before (including 409 "No recent footage. Walk past the camera, then try again."). The live view cannot give a frame when the browser has no WebRTC, `POST /api/camera/live` fails, or the connection fails. Any live session already opened SHALL be ended. If the live view connects but fewer than 10 frames are decoded within 15 s, the camera is not sending video: the app SHALL NOT fall back, and the screen SHALL show "The camera isn't sending video. Check that it's plugged in." with "Try again".

#### Scenario: Live route unavailable
- **WHEN** `POST /api/camera/live` answers 502 and `POST /api/camera/snapshot` answers 200
- **THEN** the screen shows the image from `POST /api/camera/snapshot` and `POST /api/camera/frame` is not requested

#### Scenario: No frames in time
- **WHEN** the live view connects but decodes no frames for 15 s (the camera is unplugged)
- **THEN** `DELETE /api/camera/live/{session_id}` is requested, `POST /api/camera/snapshot` is not requested, and the screen shows "The camera isn't sending video. Check that it's plugged in." with "Try again"

#### Scenario: Connection fails before any frame
- **WHEN** the connection state becomes `failed` before 10 frames are decoded
- **THEN** `DELETE /api/camera/live/{session_id}` is requested and `POST /api/camera/snapshot` is requested once

#### Scenario: Browser without WebRTC
- **WHEN** the browser has no WebRTC
- **THEN** `POST /api/camera/live` is not requested and `POST /api/camera/snapshot` is requested once

#### Scenario: Fallback finds no footage
- **WHEN** the live view fails and `POST /api/camera/snapshot` answers 409 `{"error": "no recent footage"}`
- **THEN** "No recent footage. Walk past the camera, then try again." is shown with "Try again"

#### Scenario: Screen closed while taking the snapshot
- **WHEN** the owner closes the sheet while the live view is connecting or playing
- **THEN** the live session is ended, no frame is sent, and no snapshot request follows

### Requirement: Users' snapshots from the newest recording
When a user (not the owner) is signed in and a setup screen asks for a camera snapshot with "Mock video" off, the app SHALL request `POST /api/camera/snapshot` once and handle its answer as before (including 409 "No recent footage. Walk past the camera, then try again."). It SHALL NOT request `POST /api/camera/live`, `DELETE /api/camera/live/{session_id}` or `POST /api/camera/frame`.

#### Scenario: User takes a reference snapshot
- **WHEN** a user taps "Camera snapshot" in Reference images and `POST /api/camera/snapshot` answers 200
- **THEN** the reference form shows the returned image, and `POST /api/camera/live` and `POST /api/camera/frame` are not requested

#### Scenario: User snapshot with no recent footage
- **WHEN** a user taps "Camera snapshot" in Reference images and `POST /api/camera/snapshot` answers 409
- **THEN** the screen shows "No recent footage. Walk past the camera, then try again." and `POST /api/camera/live` is not requested

#### Scenario: User snapshot fails
- **WHEN** a user asks for a snapshot in Fridge area and `POST /api/camera/snapshot` answers 502
- **THEN** the screen shows the message it shows today for a 502 from that route, and `POST /api/camera/live` is not requested

### Requirement: Online check before a snapshot
When a setup screen asks for a camera snapshot and "Mock video" is off, the app SHALL first request `GET /api/camera`. If the answer has `online: false`, the screen SHALL show "The camera is offline. Check that it's plugged in and connected to Wi-Fi." with a way to try again, and SHALL NOT open a live view, request `POST /api/camera/frame`, or fall back to `POST /api/camera/snapshot`. Otherwise the snapshot SHALL proceed as before.

#### Scenario: Reference image while the camera is offline
- **WHEN** the owner taps "Camera snapshot" in Reference images and `GET /api/camera` answers 200 with `online: false`
- **THEN** the form shows "The camera is offline. Check that it's plugged in and connected to Wi-Fi.", shows no image, keeps "Camera snapshot" and "Choose photo" enabled, and `POST /api/camera/live`, `POST /api/camera/frame` and `POST /api/camera/snapshot` are not requested

#### Scenario: Door reference while the camera is offline
- **WHEN** the owner taps "Add" in Open/close detection and `GET /api/camera` answers `online: false`
- **THEN** the sheet shows the offline message with "Try again", and no live view is opened

#### Scenario: Camera online
- **WHEN** `GET /api/camera` answers `online: true`
- **THEN** the snapshot is taken from a live frame as before

#### Scenario: Status unknown
- **WHEN** `GET /api/camera` answers `online: null`, or fails with 502 or a network error
- **THEN** the snapshot proceeds as if the camera were online

#### Scenario: Mock video on
- **WHEN** "Mock video" is on and the owner taps "Camera snapshot"
- **THEN** `GET /api/camera` is not requested for the snapshot and the clip picker opens
