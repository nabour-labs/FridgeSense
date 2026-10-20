# Spec Delta

## REMOVED Requirements

### Requirement: Door setup pictures from recent clips
**Reason**: Replaced by "Door setup pictures from live or a recent clip", which offers both sources.
**Migration**: None.

### Requirement: Live-picture zones and references marked for replacement
**Reason**: Live pictures are accepted again; replaced by "Live-picture zones and references noted".
**Migration**: None.

## ADDED Requirements

### Requirement: Door setup pictures from live or a recent clip
In Open/close detection, "Add zone", "Edit zone" and "Add reference" SHALL open with a live snapshot (`cameraSnapshot`), as the Fridge area sheet does. Under the picture, "New snapshot" SHALL take another live snapshot and "Recent clip" SHALL open the "Snapshot from a recent clip" picker, whose frame replaces the shown picture. Cancelling the picker SHALL close only the picker. The app SHALL send `source = "live"` when the shown picture is a live snapshot and `source = "clip"` when it is a clip frame. While "Mock video" is on, the snapshot comes from the mock clip picker and `source = "clip"` is sent. When the snapshot fails, the error SHALL be shown with "Try again" and "Recent clip".

#### Scenario: Reference from a live snapshot
- **WHEN** zone "Doors" exists, the owner taps "Add reference", the live snapshot is shown, and the owner picks "Closed" and taps "Save"
- **THEN** `POST /api/door-calibration/references` is sent with the snapshot image, Doors' `zone_id`, status `closed` and `source = "live"`

#### Scenario: Reference from a recent clip
- **WHEN** the owner taps "Add reference", then "Recent clip", picks a frame and taps "Use this frame", `POST /api/camera/frame` answers 200, and the owner picks "Open" and taps "Save"
- **THEN** the reference is sent with the returned clip frame and `source = "clip"`

#### Scenario: Back to live after a clip frame
- **WHEN** a clip frame is shown and the owner taps "New snapshot"
- **THEN** a new live snapshot replaces it, and Save sends `source = "live"`

#### Scenario: Zone drawn on a live snapshot
- **WHEN** the owner taps "Add zone", draws a box on the live snapshot, names it "Doors" and taps "Save"
- **THEN** `POST /api/door-calibration/zones` is sent with the name, the box and `source = "live"`

#### Scenario: Zone redrawn on a clip frame
- **WHEN** the owner edits zone "Doors", taps "Recent clip", uses a frame, draws a box and taps "Save"
- **THEN** `PATCH /api/door-calibration/zones/{id}` is sent with the box and `source = "clip"`

#### Scenario: Rename keeps the source
- **WHEN** the owner edits zone "Doors", changes only its name to "Fridge doors" and taps "Save"
- **THEN** `PATCH /api/door-calibration/zones/{id}` is sent with `{"name": "Fridge doors"}` only, so the zone keeps its box and `source`

#### Scenario: Picker cancelled
- **WHEN** the owner taps "Recent clip" and then "Cancel" in the picker
- **THEN** the sheet stays open with the live snapshot, and no request is sent

#### Scenario: No recent clips
- **WHEN** no door opening in the last 7 days has a clip and the owner taps "Recent clip"
- **THEN** the picker says "No door openings with a clip in the last 7 days." and "Use this frame" is disabled

#### Scenario: Camera offline
- **WHEN** the live snapshot fails because the camera is offline
- **THEN** the sheet shows the camera's error with "Try again" and "Recent clip"

#### Scenario: Mock video on
- **WHEN** "Mock video" is on and the owner taps "Add reference", a mock clip frame is shown, and the owner picks a zone and a status and taps "Save"
- **THEN** the reference is sent with `source = "clip"`

### Requirement: Live-picture zones and references noted
In Open/close detection, each zone and reference with `source = "live"` SHALL show the note "Live picture: may not line up with clips". The note SHALL NOT disable "Run setup".

#### Scenario: Live reference noted
- **WHEN** the tab loads zone "Doors" with `source = "clip"`, an open reference with `source = "clip"` and a closed one with `source = "live"`
- **THEN** only the closed reference shows the note, and "Run setup" is enabled

#### Scenario: Live zone noted
- **WHEN** the tab loads a zone with `source = "live"` that has an open and a closed reference
- **THEN** the zone shows the note and "Run setup" is enabled
