# Spec Delta

## Purpose

Tells the owner about setup problems that silently stop door openings from being recorded or detected correctly, and what fixes each one.

## ADDED Requirements

### Requirement: Read setup warnings
`GET /api/warnings` SHALL return 200 `{"warnings": [...], "checked_at": "<ISO 8601 UTC>"}` for the account's first discovered device. Each warning is `{"code", "message"}` plus any fields its requirement adds. Warnings are listed in this order: `motion_detection_off`, `door_setup_missing`, `camera_moved`. Owner and viewer tokens SHALL both be accepted.

#### Scenario: All set up
- **WHEN** Ring reports motion detection on, setup has run, and the camera is not moved
- **THEN** the response is 200 with `warnings = []`

#### Scenario: Several warnings in order
- **WHEN** motion detection is off and setup never ran
- **THEN** `warnings` lists `motion_detection_off` then `door_setup_missing`

#### Scenario: No token
- **WHEN** `GET /api/warnings` is called without a token
- **THEN** the response is 401 `{"error": "sign in"}`

#### Scenario: No camera yet
- **WHEN** the account has no discovered device
- **THEN** the response is 200 with `warnings = []`

### Requirement: Motion detection off warning
When Ring's device details report `motion_detection` as off, the list SHALL include `{"code": "motion_detection_off", "message": "Motion detection is off on the camera, so no door openings are recorded. Turn it on in the Ring app."}`. When Ring cannot be reached, or does not report the setting, this warning SHALL be left out and the response SHALL still be 200.

#### Scenario: Motion detection off
- **WHEN** Ring's device response has `configurations.motion_detection.enabled = "off"`
- **THEN** the list includes the `motion_detection_off` warning with that message

#### Scenario: Ring unreachable
- **WHEN** the Ring device call times out or answers 500
- **THEN** the response is 200 without `motion_detection_off`, and the other warnings are still checked

### Requirement: Door setup missing warning
When the device has no setup result, the list SHALL include `{"code": "door_setup_missing", "message": "Open/close detection is not set up, so the default zones are used and openings may be missed."}`.

#### Scenario: Setup never run
- **WHEN** door references exist but setup never ran successfully
- **THEN** the list includes `door_setup_missing`

#### Scenario: Setup run
- **WHEN** setup has run successfully
- **THEN** `door_setup_missing` is not listed

### Requirement: Camera moved warning
The list SHALL include `{"code": "camera_moved", "message": "The camera has moved or changed angle. Update the references so detection stays accurate.", "since": "<last_moved_at>", "update": [...]}` whenever `update` is not empty. `update` holds `"door_references"` while the alignment reads moved, and `"fridge_area"` while a fridge area exists that was saved before the alignment's `last_moved_at`. A setup run removes `"door_references"`. Saving the fridge area again removes `"fridge_area"`.

#### Scenario: Both need updating
- **WHEN** the camera moved at 10:00 and the fridge area was saved the day before
- **THEN** the warning has `since` = 10:00 and `update = ["door_references", "fridge_area"]`

#### Scenario: Fridge area already updated
- **WHEN** the camera moved at 10:00 and the fridge area was saved at 10:30
- **THEN** `update = ["door_references"]`

#### Scenario: No fridge area
- **WHEN** the camera moved and no fridge area was ever saved
- **THEN** `update = ["door_references"]`

#### Scenario: Setup run but fridge area not updated
- **WHEN** the camera moved at 10:00, the fridge area is from the day before, and the owner runs setup successfully at 10:15
- **THEN** the warning is still listed with `update = ["fridge_area"]`

#### Scenario: Both updated
- **WHEN** after the move the owner runs setup and saves the fridge area again
- **THEN** `camera_moved` is not listed
