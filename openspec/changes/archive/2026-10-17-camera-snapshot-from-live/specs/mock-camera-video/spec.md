# Spec Delta

## MODIFIED Requirements

### Requirement: Snapshots come from a clip while the switch is on
While "Mock video" is on, every camera snapshot request in the app SHALL open the clip picker instead of taking a live frame or calling `POST /api/camera/snapshot`. This covers "Camera snapshot" in Reference images, and in Open/close detection and Fridge area both the snapshot taken when the add or set-area sheet opens and "New snapshot". While it is off, snapshots are taken from a live frame, with `POST /api/camera/snapshot` as the fallback.

#### Scenario: Reference image from a clip
- **WHEN** the switch is on and the owner taps "Camera snapshot" in Reference images, picks a frame and taps "Use this frame"
- **THEN** `POST /api/camera/live`, `POST /api/camera/frame` and `POST /api/camera/snapshot` are not requested and the reference form shows that frame as its image

#### Scenario: Door reference from a clip
- **WHEN** the switch is on and the owner taps "Add" in Open/close detection
- **THEN** the clip picker opens, and after "Use this frame" the frame is shown for drawing the door box

#### Scenario: Switch off
- **WHEN** the switch is off and the owner taps "Camera snapshot"
- **THEN** `POST /api/camera/live` is requested once and no clip picker opens

#### Scenario: Cancel
- **WHEN** the clip picker is open and the owner taps "Cancel" or closes the sheet
- **THEN** the picker closes, the screen shows no new snapshot and no error message, and no request is made
