# Spec Delta

## ADDED Requirements

### Requirement: Door setup pictures from recent clips
In Open/close detection, "Add zone", "Edit zone" (for a new box) and "Add reference" SHALL get their picture from the recent-clip frame picker ("Snapshot from a recent clip"), not from the live view or the Ring still. Its "New snapshot" control SHALL read "Another frame" and reopen the picker. The app SHALL send `source = "clip"` with the zone or reference. While "Mock video" is on, the mock clip picker is used instead, and `source = "clip"` is still sent.

#### Scenario: Reference from a recent clip
- **WHEN** zone "Doors" exists, the owner taps "Add reference", picks the 18:02 opening, scrubs to a frame with the doors closed, taps "Use this frame", `POST /api/camera/frame` answers 200, and the owner picks "Closed" and taps "Save"
- **THEN** `POST /api/camera/live` and `POST /api/camera/snapshot` are not requested, and `POST /api/door-calibration/references` is sent with the returned image, Doors' `zone_id`, status `closed` and `source = "clip"`

#### Scenario: Zone drawn on a clip frame
- **WHEN** the owner taps "Add zone", uses a frame from a recent clip, draws a box, names it "Doors" and taps "Save"
- **THEN** `POST /api/door-calibration/zones` is sent with the name, the box and `source = "clip"`

#### Scenario: Another frame
- **WHEN** a clip frame is shown in the add-reference sheet and the owner taps "Another frame"
- **THEN** the recent-clip picker opens again, and the frame it returns replaces the shown one

#### Scenario: No recent clips
- **WHEN** no door opening in the last 7 days has a clip and the owner taps "Add reference"
- **THEN** the picker says "No door openings with a clip in the last 7 days." and "Use this frame" is disabled

#### Scenario: Picker cancelled
- **WHEN** the owner taps "Cancel" in the picker opened by "Add reference"
- **THEN** the add-reference sheet closes and no request is sent

#### Scenario: Mock video on
- **WHEN** "Mock video" is on and the owner taps "Add reference", picks a mock clip frame, a zone and a status, and taps "Save"
- **THEN** the reference is sent with `source = "clip"`

### Requirement: Live-picture zones and references marked for replacement
In Open/close detection, each zone and reference with `source = "live"` SHALL show the note "Replace with a clip frame". While any is shown, "Run setup" SHALL be disabled, with the hint "Replace the zones and references marked 'Replace with a clip frame' first."

#### Scenario: Old references marked
- **WHEN** the tab loads zone "Doors" with `source = "clip"`, one reference with `source = "clip"` and one with `source = "live"`
- **THEN** only the second reference shows "Replace with a clip frame", and "Run setup" is disabled with that hint

#### Scenario: Old zone marked
- **WHEN** the tab loads a zone with `source = "live"`
- **THEN** the zone shows "Replace with a clip frame" and "Run setup" is disabled

#### Scenario: All from clips
- **WHEN** every zone and reference has `source = "clip"` and each zone has an open and a closed reference
- **THEN** no "Replace with a clip frame" note is shown and "Run setup" is enabled

### Requirement: Setup mismatch banner
The warning banner for `door_setup_mismatch` SHALL show its `message` with an "Update door references" link to `#config/doors`. Viewers see the message without the link.

#### Scenario: Mismatch banner
- **WHEN** an owner opens the Fridge screen and `GET /api/warnings` lists `door_setup_mismatch`
- **THEN** the banner shows its message and an "Update door references" link to `#config/doors`

#### Scenario: Viewer sees no link
- **WHEN** a viewer opens the Fridge screen and the warnings list `door_setup_mismatch`
- **THEN** the banner shows its message with no link
