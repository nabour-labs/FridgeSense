# Spec Delta

## ADDED Requirements

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
