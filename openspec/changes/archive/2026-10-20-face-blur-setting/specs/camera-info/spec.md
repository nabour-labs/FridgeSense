# Spec Delta

## MODIFIED Requirements

### Requirement: Camera tab
The Config "Camera" tab SHALL show the camera's product image and name, an "Online" or "Offline" badge (or "Unknown" when `online` is null), the manufacturer, video codecs, aspect ratio, max and supported resolutions (as "1080p"), image enhancements with On/Off, motion detection, end-to-end encryption and location. Values Ring did not report SHALL show as "Not reported". The camera details SHALL be read-only for every role. The tab also holds the "Blur faces" switch (see `face-blur-setting`), which only the owner sees.

#### Scenario: Camera tab shows details
- **WHEN** `GET /api/camera` answers with the details from the fixture
- **THEN** the tab shows "Fridge Cam", an "Online" badge, "Ring", "AVC", "16:9", "1080p", "HDR" with "On", "Motion detection" with "On" and "End-to-end encryption" with "Off"

#### Scenario: Camera offline
- **WHEN** `GET /api/camera` answers `online: false`
- **THEN** the badge reads "Offline"

#### Scenario: Ring unreachable
- **WHEN** `GET /api/camera` answers `ring: "unavailable"`
- **THEN** the badge reads "Unknown", the tab says "Could not reach the camera service. Showing saved details.", and the video fields show "Not reported"

#### Scenario: No camera linked
- **WHEN** `GET /api/camera` answers 409 `{"error": "no camera linked"}`
- **THEN** the tab shows "No camera is linked yet." and no "Something went wrong" notice

#### Scenario: Only the blur switch is editable
- **WHEN** the owner opens the Camera tab
- **THEN** the "Blur faces" switch is the only enabled control that changes data
