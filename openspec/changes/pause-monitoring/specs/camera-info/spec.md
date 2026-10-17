# Spec Delta

## MODIFIED Requirements

### Requirement: Camera tab
The Config "Camera" tab SHALL show the camera's product image and name, an "Online" or "Offline" badge (or "Unknown" when `online` is null), the manufacturer, video codecs, aspect ratio, max and supported resolutions (as "1080p"), image enhancements with On/Off, motion detection, end-to-end encryption and location. Values Ring did not report SHALL show as "Not reported". The camera details SHALL be read-only for every role. The tab also holds the "FridgeSense" monitoring switch, which owners and users can change, and the "Blur faces" switch (see `face-blur-setting`), which only the owner can change.

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

#### Scenario: Only the two switches are editable
- **WHEN** the owner opens the Camera tab
- **THEN** the "FridgeSense" and "Blur faces" switches are the only enabled controls that change data

## ADDED Requirements

### Requirement: Monitoring switch on the Camera tab
The Camera tab SHALL start with a "FridgeSense" card showing "Active" or "Paused since <local date and time>" from `monitoring`, and the line "Pause while you clean, service or renovate. Door openings are not recorded or analyzed while paused." Owners and users SHALL get a switch labelled "FridgeSense" that sends `PUT /api/camera/monitoring` with the opposite state and then shows the returned state. Viewers SHALL see the state without the switch.

#### Scenario: Active camera
- **WHEN** an owner opens the Camera tab and `monitoring` is `{"paused": false, "since": null}`
- **THEN** the card reads "Active" and the "FridgeSense" switch is on

#### Scenario: Pause from the tab
- **WHEN** the owner turns the switch off and the API answers `{"paused": true, "since": "2026-10-18T14:05:00.000Z"}`
- **THEN** `PUT /api/camera/monitoring` was sent with `{"paused": true}`, the switch is off, and the card reads "Paused since" with that time in local time

#### Scenario: Resume from the tab
- **WHEN** the camera is paused and the owner turns the switch on
- **THEN** `PUT /api/camera/monitoring` was sent with `{"paused": false}` and the card reads "Active"

#### Scenario: Change fails
- **WHEN** the owner turns the switch and the request answers 500
- **THEN** the switch returns to its previous position and the card shows "Could not change it. Try again."

#### Scenario: Viewer
- **WHEN** a viewer opens the Camera tab while the camera is paused
- **THEN** the card reads "Paused since …" and there is no switch
