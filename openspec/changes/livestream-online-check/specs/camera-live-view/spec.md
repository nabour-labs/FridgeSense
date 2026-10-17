# Spec Delta

## ADDED Requirements

### Requirement: Online check before a live view
Each time the Livestream dialog starts a live view (when it opens, and on "Try again" or "Watch again"), the app SHALL first request `GET /api/camera`. If the answer has `online: false`, the dialog SHALL show "The camera is offline. Check that it's plugged in and connected to Wi-Fi." and "Try again", and SHALL NOT create a peer connection or call `POST /api/camera/live`. Otherwise the live view SHALL start as before.

#### Scenario: Camera offline
- **WHEN** the owner taps "Livestream" and `GET /api/camera` answers 200 with `online: false`
- **THEN** the dialog shows "The camera is offline. Check that it's plugged in and connected to Wi-Fi." and "Try again", no peer connection is created, and `POST /api/camera/live` is not requested

#### Scenario: Camera online
- **WHEN** `GET /api/camera` answers 200 with `online: true`
- **THEN** the dialog shows "Connecting…" and requests `POST /api/camera/live` with the browser's offer

#### Scenario: Status unknown
- **WHEN** `GET /api/camera` answers 200 with `online: null` (Ring unreachable), or fails with 502 or a network error
- **THEN** the live view starts as if the camera were online, and no global error notice is raised

#### Scenario: Try again after offline
- **WHEN** the dialog shows the offline message, the camera comes back, and the owner taps "Try again" and `GET /api/camera` now answers `online: true`
- **THEN** `GET /api/camera` is requested a second time and `POST /api/camera/live` is requested once

#### Scenario: Closed during the check
- **WHEN** the dialog is closed before `GET /api/camera` answers
- **THEN** no peer connection is created and `POST /api/camera/live` is not requested

### Requirement: No black picture while connecting
The dialog SHALL show "Connecting…" in the video area from the moment it opens until the video starts playing. It SHALL NOT show an empty black video box with no message.

#### Scenario: Track arrived, video not playing yet
- **WHEN** the video track has arrived but the video has not started playing
- **THEN** the dialog shows "Connecting…" over the video area and the countdown

#### Scenario: Video plays
- **WHEN** the video starts playing
- **THEN** "Connecting…" is no longer shown
