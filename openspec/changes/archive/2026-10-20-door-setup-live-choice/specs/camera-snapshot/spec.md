# Spec Delta

## MODIFIED Requirements

### Requirement: Snapshot from a live frame
When the owner is signed in, a setup screen asks for a camera snapshot ("Camera snapshot" in Reference images, the set-area sheet and "New snapshot" in Fridge area, and the zone and add-reference sheets and their "New snapshot" in Open/close detection) and "Mock video" is off, the app SHALL open a live view (`POST /api/camera/live`), wait until at least 10 video frames have been decoded, draw the current frame as a JPEG at most 960 px wide, end the live session (`DELETE /api/camera/live/{session_id}`), and send the frame to `POST /api/camera/frame`. The screen SHALL show only the image that route returns.

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

#### Scenario: Open/close detection takes a live frame
- **WHEN** "Mock video" is off and the owner taps "Add reference" in Open/close detection
- **THEN** the sheet asks `cameraSnapshot` for a live frame and shows the returned image
