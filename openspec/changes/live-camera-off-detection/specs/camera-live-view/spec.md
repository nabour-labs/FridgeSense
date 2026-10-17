# Spec Delta

## MODIFIED Requirements

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
