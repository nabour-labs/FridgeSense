# setup-warnings Specification

## Purpose
Lists the setup problems that silently stop door openings being recorded or detected well, through `GET /api/warnings` and the app's warning banner, each with what fixes it.

## Requirements

### Requirement: Ring account needs re-linking warning
When the stored Ring account has `link_status = "needs_relink"`, `GET /api/warnings` SHALL list `{"code": "needs_relink", "message": "The Ring account link has expired, so door openings are not recorded. Re-link the Ring account in the Ring app."}` before every other warning, even when no camera has been discovered. The other warnings SHALL still be checked. In the app, the banner SHALL show the message with no fix link.

#### Scenario: Link expired
- **WHEN** the token store holds `link_status = "needs_relink"` and every other check passes
- **THEN** `warnings` is `[{"code": "needs_relink", "message": "The Ring account link has expired, so door openings are not recorded. Re-link the Ring account in the Ring app."}]`

#### Scenario: Link expired with other problems
- **WHEN** the link needs re-linking and door setup never ran
- **THEN** `warnings` lists `needs_relink` then `door_setup_missing`

#### Scenario: Link expired before any camera
- **WHEN** the link needs re-linking and no camera has been discovered
- **THEN** `warnings` is the `needs_relink` warning alone

#### Scenario: Linked
- **WHEN** the token store holds `link_status = "linked"`
- **THEN** no `needs_relink` warning is listed

#### Scenario: Re-link banner
- **WHEN** an owner opens the Fridge screen and `GET /api/warnings` lists `needs_relink`
- **THEN** the banner shows its message and no link

### Requirement: Privacy mask changed warning
`GET /api/warnings` SHALL include `{"code": "privacy_mask_changed", "message": "The camera's privacy mask changed and now covers part of <zones>. Move those door zones or the mask, then retake their door references.", "since": "<mask_changed_at>", "zones": [...]}` while the device's alignment has a non-empty `mask_zones`. `<zones>` SHALL be the zone names joined as "A", "A and B", or "A, B and C", and `zones` SHALL list the same names. A mask change SHALL never add `camera_moved`. If the alignment can't be read, the warning SHALL be left out and the other warnings still returned.

#### Scenario: One zone covered
- **WHEN** the alignment has `mask_zones = ["Chiller"]` and `mask_changed_at` = 2026-10-18T21:32:14Z
- **THEN** the warnings include `{"code": "privacy_mask_changed", "message": "The camera's privacy mask changed and now covers part of Chiller. Move those door zones or the mask, then retake their door references.", "since": "2026-10-18T21:32:14.000Z", "zones": ["Chiller"]}`

#### Scenario: Three zones covered
- **WHEN** `mask_zones = ["Chiller", "Freezer Drawer 1", "Freezer Drawer 2"]`
- **THEN** the message says "covers part of Chiller, Freezer Drawer 1 and Freezer Drawer 2"

#### Scenario: Mask change with no zone covered
- **WHEN** the mask changed but `mask_zones` is empty and `moved` is false
- **THEN** neither `privacy_mask_changed` nor `camera_moved` is listed

#### Scenario: Cleared by a setup run
- **WHEN** `mask_zones = ["Chiller"]` and the owner runs setup successfully
- **THEN** `privacy_mask_changed` is no longer listed

#### Scenario: Alignment unreadable
- **WHEN** reading the alignment item raises an error
- **THEN** `GET /api/warnings` answers 200 without `privacy_mask_changed` and with the other warnings

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

### Requirement: Monitoring paused warning
When the account's first discovered camera is paused, `GET /api/warnings` SHALL list `{"code": "monitoring_paused", "message": "FridgeSense is paused, so door openings are not recorded.", "since": "<ISO 8601 UTC>"}` before every other warning. The other warnings SHALL still be checked. In the app, the banner's fix link for this warning SHALL read "Resume on Camera tab" and go to `#config`.

#### Scenario: Paused
- **WHEN** the camera was paused at `2026-10-18T14:05:00.000Z`
- **THEN** `warnings[0]` is `{"code": "monitoring_paused", "message": "FridgeSense is paused, so door openings are not recorded.", "since": "2026-10-18T14:05:00.000Z"}`

#### Scenario: Paused with other problems
- **WHEN** the camera is paused and door setup never ran
- **THEN** `warnings` lists `monitoring_paused` then `door_setup_missing`

#### Scenario: Active
- **WHEN** the camera is active
- **THEN** no `monitoring_paused` warning is listed

#### Scenario: Banner link
- **WHEN** an owner opens the Fridge screen and `GET /api/warnings` lists `monitoring_paused`
- **THEN** the banner shows its message and a "Resume on Camera tab" link to `#config`; a viewer sees the message without the link

### Requirement: Door setup mismatch warning
When the device's `suspect_streak` is 3 or more, `GET /api/warnings` SHALL list `{"code": "door_setup_mismatch", "message": "Open/close detection doesn't match the camera's recordings, so the fridge light is used instead. Replace the door references with frames from recent clips and run setup again."}`. It SHALL come after every other warning. When the streak cannot be read, the warning SHALL be left out and the response SHALL still be 200.

#### Scenario: Three suspect events
- **WHEN** the device's `suspect_streak` is 3
- **THEN** `warnings` includes `door_setup_mismatch` with that message

#### Scenario: Two suspect events
- **WHEN** the device's `suspect_streak` is 2
- **THEN** `door_setup_mismatch` is not listed

#### Scenario: Listed last
- **WHEN** setup never ran and the `suspect_streak` is 4
- **THEN** `warnings` lists `door_setup_missing` before `door_setup_mismatch`

#### Scenario: Cleared by setup
- **WHEN** the streak was 3 and the owner runs setup successfully
- **THEN** `door_setup_mismatch` is no longer listed

#### Scenario: Streak unreadable
- **WHEN** reading the streak raises a table error
- **THEN** the response is 200 without `door_setup_mismatch`
