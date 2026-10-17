# Spec Delta

## MODIFIED Requirements

### Requirement: Config screen
The app SHALL offer a Config screen, opened by a "Config" gear button in the header. Its tabs are "Camera" at `#config` (the default), "Reference images" at `#config/refs`, "Open/close detection" at `#config/doors`, "Fridge area" at `#config/fridge` and, for the owner only, "Debug" at `#config/debug`. Switching tabs SHALL update the hash, and opening any of these hashes SHALL show that tab. The tabs SHALL fit side by side at 375 px without horizontal scrolling. Viewers get no edit controls.

#### Scenario: Open config
- **WHEN** the signed-in user taps the gear button
- **THEN** the header title reads "Config", the "Camera" tab is selected, `GET /api/camera` is requested, and the location hash is `#config`

#### Scenario: Reference images tab
- **WHEN** the user selects the "Reference images" tab
- **THEN** the location hash is `#config/refs`, `GET /api/config` is requested, and the "Reference images" and "Custom instructions" sub-sections are shown

#### Scenario: Direct link to reference images
- **WHEN** the app opens at `#config/refs`
- **THEN** the "Reference images" tab is selected

#### Scenario: Switch to open/close detection
- **WHEN** the user taps the "Open/close detection" tab
- **THEN** the hash becomes `#config/doors`, `GET /api/door-calibration` is requested, and the door references are shown

#### Scenario: Switch to fridge area
- **WHEN** the user taps the "Fridge area" tab
- **THEN** the hash becomes `#config/fridge` and `GET /api/fridge-area` is requested

#### Scenario: Switch to debug
- **WHEN** the owner taps the "Debug" tab
- **THEN** the hash becomes `#config/debug` and `GET /api/debug/motions` is requested

#### Scenario: Open the detection tab by link
- **WHEN** the app is opened at `#config/doors`
- **THEN** the Config screen shows with the "Open/close detection" tab selected

#### Scenario: Open the fridge area tab by link
- **WHEN** the app is opened at `#config/fridge`
- **THEN** the Config screen shows with the "Fridge area" tab selected

#### Scenario: Owner's tabs
- **WHEN** the owner opens Config
- **THEN** the tabs are "Camera", "Reference images", "Open/close detection", "Fridge area" and "Debug", in one row

#### Scenario: Non-owner opens the debug link
- **WHEN** a viewer or user opens `#config/debug`
- **THEN** the "Reference images" tab is shown, as before, and no `/api/debug` request is made

#### Scenario: Viewer sees read-only config
- **WHEN** a viewer opens the "Reference images" tab and the config has one reference and instructions
- **THEN** the reference thumbnail, its annotation and the instructions are shown, with no "Add", "Delete" or "Save" controls

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
