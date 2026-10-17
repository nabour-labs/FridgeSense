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

### Requirement: Manage reference images
The "Reference images" sub-section SHALL list each reference as a thumbnail with its annotation (its description). It SHALL let the owner add one and delete one after confirming. Adding SHALL offer two sources: "Choose photo" (pick or take a photo on the device) and "Camera snapshot" (`POST /api/camera/snapshot`). Once an image is chosen, the owner SHALL be able to draw on it with a "Box" tool and a "Line" tool, undo the last shape with "Undo", and type the annotation. The shapes SHALL be drawn in red into the uploaded image. Before upload, the image SHALL be re-encoded as JPEG with its longer side at most 768 px. The owner SHALL see how many of the 6 are used.

#### Scenario: Add a reference
- **WHEN** the owner taps "Add", taps "Choose photo", picks a 4032×3024 photo, types `soda can` and taps "Save"
- **THEN** `POST /api/config/references` is sent with annotation `soda can` and a JPEG of 768×576, and the list shows the new thumbnail labeled "soda can"

#### Scenario: Add a camera snapshot
- **WHEN** the owner taps "Add", then "Camera snapshot", and the API answers 200 with a 960×540 image
- **THEN** that image is shown for drawing, and after typing `milk bag` and tapping "Save", the uploaded JPEG is 768×432

#### Scenario: Snapshot with no recent footage
- **WHEN** the API answers 409 `{"error": "no recent footage"}` to a snapshot
- **THEN** "No recent footage. Walk past the camera, then try again." is shown and the owner can still choose a photo

#### Scenario: Draw on the image
- **WHEN** the owner selects "Box", drags from 10%, 10% to 40%, 50% of the image, selects "Line", drags from 50%, 50% to 90%, 90%, and taps "Save"
- **THEN** the shapes passed to the upload are a box from `(0.1, 0.1)` to `(0.4, 0.5)` and a line from `(0.5, 0.5)` to `(0.9, 0.9)`, in that order, drawn in red into the JPEG

#### Scenario: Undo a shape
- **WHEN** the owner has drawn two shapes and taps "Undo"
- **THEN** only the first shape remains, and "Undo" is disabled when no shapes are left

#### Scenario: Annotation required
- **WHEN** the owner picks a photo but leaves the annotation empty
- **THEN** "Save" is disabled and no request is sent

#### Scenario: Limit reached
- **WHEN** 6 references exist
- **THEN** the sub-section shows "6 of 6" and the "Add" button is disabled

#### Scenario: Delete a reference
- **WHEN** the owner taps "Delete" on "milk bag" and confirms
- **THEN** `DELETE /api/config/references/{id}` is sent and "milk bag" disappears from the list

#### Scenario: Upload refused
- **WHEN** the API answers 400 or 409 to an add
- **THEN** the error message from the response is shown and the list is unchanged

## ADDED Requirements

### Requirement: Open/close detection tab
The "Open/close detection" tab SHALL list the door references as thumbnails, each with its box drawn on it, an "Open" or "Closed" badge, and its score as a percentage with one decimal (or "–" when it has none), oldest first, with "n of 12" shown. The owner SHALL be able to add a reference: tapping "Add" requests a camera snapshot, the owner drags on it to draw one box (a new drag replaces the box), picks "Open" or "Closed", and taps "Save" to send `POST /api/door-calibration/references`. The owner SHALL be able to delete a reference after confirming. A "Run setup" button SHALL send `POST /api/door-calibration/run`. It is enabled only when there is at least one open and one closed reference. The tab SHALL show the setup state:
- "Not set up yet. Using default zones." when `setup` is null.
- One line per setup zone when `setup` exists: "Zone n: <Color | Brightness | Change> above (or below) t%, margin m%".
- "References changed. Run setup again." when `setup.stale` is true.

#### Scenario: References shown
- **WHEN** the tab loads two references, open with score 0.1 and closed with score 0.0, and a setup with one zone using `color` above 0.05 with margin 0.1
- **THEN** both thumbnails show their boxes, the badges read "Open" and "Closed", the scores read "10.0%" and "0.0%", "2 of 12" is shown, and the state reads "Zone 1: Color above 5.0%, margin 10.0%"

#### Scenario: Not set up
- **WHEN** the tab loads with no references and `setup = null`
- **THEN** "Not set up yet. Using default zones." is shown and "Run setup" is disabled

#### Scenario: Add a door reference
- **WHEN** the owner taps "Add", the snapshot answers 200, the owner drags from 38%, 32% to 59%, 62% of the image, taps "Open" and taps "Save"
- **THEN** `POST /api/door-calibration/references` is sent with the snapshot image, box `{"x": 0.38, "y": 0.32, "width": 0.21, "height": 0.3}` and status `open`, and the list shows the new reference

#### Scenario: Box and status required
- **WHEN** the snapshot is shown but no box is drawn, or no status is picked
- **THEN** "Save" is disabled and no request is sent

#### Scenario: Redraw replaces the box
- **WHEN** the owner draws one box and then drags again elsewhere
- **THEN** only the second box is shown and sent

#### Scenario: Tiny drag ignored
- **WHEN** the owner drags less than 2% of the image's width or height
- **THEN** no box is drawn

#### Scenario: Snapshot fails while adding
- **WHEN** the API answers 409 `{"error": "no recent footage"}` to the snapshot
- **THEN** "No recent footage. Walk past the camera, then try again." is shown with a "Try again" button that requests a new snapshot

#### Scenario: Delete a door reference
- **WHEN** the owner taps "Delete" on a reference and confirms
- **THEN** `DELETE /api/door-calibration/references/{id}` is sent and the reference disappears

#### Scenario: Run setup
- **WHEN** the owner has one open and one closed reference and taps "Run setup", and the API answers 200
- **THEN** `POST /api/door-calibration/run` is sent once, the button shows a busy state until the answer, and the new setup state and scores are shown

#### Scenario: Setup fails
- **WHEN** the API answers 422 `{"error": "zone 1: open and closed references overlap", "references": [...]}`
- **THEN** that error message is shown, and the scores from the response are shown on the references

#### Scenario: Run setup needs both statuses
- **WHEN** every reference is "Closed"
- **THEN** "Run setup" is disabled, with the hint "Add at least one open and one closed reference."

#### Scenario: Stale setup
- **WHEN** `setup.stale` is true
- **THEN** "References changed. Run setup again." is shown
