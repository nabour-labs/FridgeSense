## MODIFIED Requirements

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

## ADDED Requirements

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
