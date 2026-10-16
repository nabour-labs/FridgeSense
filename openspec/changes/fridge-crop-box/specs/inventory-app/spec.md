# Spec Delta

## MODIFIED Requirements

### Requirement: Config screen
The app SHALL offer a Config screen, opened by a "Config" gear button in the header. It has three tabs: "Reference images" at `#config` (the "Reference images" and "Custom instructions" sub-sections, which guide the item analysis), "Open/close detection" at `#config/doors`, and "Fridge area" at `#config/fridge`. Switching tabs SHALL update the hash, and opening any of these hashes SHALL show that tab. The three tabs SHALL fit side by side at a 375 px wide screen without horizontal scrolling. For a viewer, all tabs are shown without add, snapshot, delete, run, set or save controls.

#### Scenario: Open config
- **WHEN** the signed-in user taps the gear button
- **THEN** the header title reads "Config", the "Reference images" tab is selected, `GET /api/config` is requested, and the "Reference images" and "Custom instructions" sub-sections are shown

#### Scenario: Switch to open/close detection
- **WHEN** the user taps the "Open/close detection" tab
- **THEN** the hash becomes `#config/doors`, `GET /api/door-calibration` is requested, and the door references are shown

#### Scenario: Switch to fridge area
- **WHEN** the user taps the "Fridge area" tab
- **THEN** the hash becomes `#config/fridge` and `GET /api/fridge-area` is requested

#### Scenario: Open the detection tab by link
- **WHEN** the app is opened at `#config/doors`
- **THEN** the Config screen shows with the "Open/close detection" tab selected

#### Scenario: Open the fridge area tab by link
- **WHEN** the app is opened at `#config/fridge`
- **THEN** the Config screen shows with the "Fridge area" tab selected

#### Scenario: Viewer sees read-only config
- **WHEN** a viewer opens Config, the config has one reference and instructions, and there are two door references
- **THEN** the reference thumbnail, its annotation, the instructions and both door references are shown, with no "Add", "Delete", "Run setup" or "Save" controls

## ADDED Requirements

### Requirement: Fridge area tab
The "Fridge area" tab SHALL show the saved fridge area as its snapshot with the box drawn on it and "Saved <date and time>", or "No fridge area yet." when `area` is null. The owner SHALL be able to set the area: tapping "Set area" (or "Change area" when one is saved) requests a camera snapshot, the owner drags on it to draw one box around the fridge (a new drag replaces the box), and taps "Save" to send `PUT /api/fridge-area` with the snapshot image and the box. "Cancel" SHALL close the editor without a request. A viewer SHALL see the saved area with no "Set area", "Change area" or "Save" control.

#### Scenario: Fridge area shown
- **WHEN** the tab loads an area with box `{"x": 0.2, "y": 0.05, "width": 0.5, "height": 0.9}`
- **THEN** the snapshot is shown with one box covering 20%–70% across and 5%–95% down, and the button reads "Change area"

#### Scenario: No fridge area
- **WHEN** the tab loads with `area = null`
- **THEN** "No fridge area yet." is shown and the button reads "Set area"

#### Scenario: Set the fridge area
- **WHEN** the owner taps "Set area", the snapshot answers 200, the owner drags from 20%, 5% to 70%, 95% of the image and taps "Save"
- **THEN** `PUT /api/fridge-area` is sent with the snapshot image and box `{"x": 0.2, "y": 0.05, "width": 0.5, "height": 0.9}`, and the tab shows the saved area

#### Scenario: Box required to save
- **WHEN** the snapshot is shown and no box is drawn
- **THEN** "Save" is disabled and no request is sent

#### Scenario: Redraw replaces the fridge box
- **WHEN** the owner draws one box and then drags again elsewhere
- **THEN** only the second box is shown and sent

#### Scenario: Cancel setting the area
- **WHEN** the owner taps "Set area", draws a box and taps "Cancel"
- **THEN** no `PUT /api/fridge-area` is sent and the saved area (or "No fridge area yet.") is shown again

#### Scenario: Snapshot fails while setting the area
- **WHEN** the API answers 409 `{"error": "no recent footage"}` to the snapshot
- **THEN** "No recent footage. Walk past the camera, then try again." is shown with a "Try again" button that requests a new snapshot

#### Scenario: Viewer sees the fridge area read-only
- **WHEN** a viewer opens the tab and an area is saved
- **THEN** the snapshot and box are shown, with no "Set area", "Change area" or "Save" control
