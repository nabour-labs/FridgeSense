# Spec Delta

## MODIFIED Requirements

### Requirement: Open/close detection tab
The "Open/close detection" tab SHALL show setup in two steps. **1. Door zones:** each zone's name, with "n of 6" (its box is shown on its references). The owner adds a zone ("Add zone": snapshot, draw one box, name it, "Save"), renames or redraws it, or deletes it after confirming. **2. References:** grouped by zone, each with its badge and score. "Add reference" needs a zone to exist and a zone and a status to be picked. The zone's box is shown on the snapshot, not drawn. "Run setup" needs every zone to have one open and one closed reference. The tab SHALL show the setup state:
- "Not set up yet. Using default zones." when `setup` is null.
- One line per setup zone when `setup` exists: "<zone name>: <Blue light | Color | Brightness | Change> above (or below) t%, margin m%".
- "Zones or references changed. Run setup again." when `setup.stale` is true.

#### Scenario: References shown
- **WHEN** the tab loads zone "Doors" with two references, open with score 0.1 and closed with score 0.0, and a setup with zone "Doors" using `color` above 0.05 with margin 0.1
- **THEN** "Doors" is listed under "Door zones", both references are listed under "Doors" with that zone's box drawn on them, the badges read "Open" and "Closed", the scores read "10.0%" and "0.0%", "2 of 24" is shown, and the state reads "Doors: Color above 5.0%, margin 10.0%"

#### Scenario: Not set up
- **WHEN** the tab loads with no zones, no references and `setup = null`
- **THEN** "Not set up yet. Using default zones." is shown, the references step reads "Add a door zone first.", "Add reference" and "Run setup" are disabled

#### Scenario: Add a door zone
- **WHEN** the owner taps "Add zone", the snapshot answers 200, the owner drags from 38%, 65% to 58%, 90% of the image, types "Freezer drawer" and taps "Save"
- **THEN** `POST /api/door-calibration/zones` is sent with `{"name": "Freezer drawer", "box": {"x": 0.38, "y": 0.65, "width": 0.2, "height": 0.25}}`, and "Freezer drawer" is listed under "Door zones"

#### Scenario: Zone needs a box and a name
- **WHEN** the zone snapshot is shown but no box is drawn, or the name is empty
- **THEN** "Save" is disabled and no request is sent

#### Scenario: Redraw replaces the box
- **WHEN** the owner draws one zone box and then drags again elsewhere
- **THEN** only the second box is shown and sent

#### Scenario: Tiny drag ignored
- **WHEN** the owner drags less than 2% of the image's width or height
- **THEN** no box is drawn

#### Scenario: Edit a zone
- **WHEN** the owner taps "Edit" on zone "Doors", changes the name to "Fridge doors", draws a new box on a new snapshot and taps "Save"
- **THEN** `PATCH /api/door-calibration/zones/{id}` is sent with the new name and box, and its references are shown with the new box

#### Scenario: Delete a zone
- **WHEN** the owner taps "Delete" on zone "Drawer" with 3 references and confirms "Delete Drawer and its 3 references?"
- **THEN** `DELETE /api/door-calibration/zones/{id}` is sent, and the zone and its references disappear

#### Scenario: Add a door reference
- **WHEN** zones "Doors" and "Drawer" exist, the owner taps "Add reference", the snapshot answers 200, the owner picks "Drawer", taps "Open" and taps "Save"
- **THEN** "Drawer"'s box is drawn on the snapshot once it is picked, `POST /api/door-calibration/references` is sent with the snapshot image, Drawer's `zone_id` and status `open`, and the new reference is listed under "Drawer"

#### Scenario: Box and status required
- **WHEN** two zones exist and the reference snapshot is shown, but no zone is picked or no status is picked
- **THEN** "Save" is disabled, no box is drawn until a zone is picked, and no request is sent

#### Scenario: Only one zone
- **WHEN** exactly one zone, "Doors", exists and the owner taps "Add reference"
- **THEN** "Doors" is already picked and its box is drawn on the snapshot

#### Scenario: Snapshot fails while adding
- **WHEN** the API answers 409 `{"error": "no recent footage"}` to the snapshot for a zone or a reference
- **THEN** "No recent footage. Walk past the camera, then try again." is shown with a "Try again" button that requests a new snapshot

#### Scenario: Delete a door reference
- **WHEN** the owner taps "Delete" on a reference and confirms
- **THEN** `DELETE /api/door-calibration/references/{id}` is sent and the reference disappears

#### Scenario: Zone checklist
- **WHEN** zone "Doors" has 2 open and 1 closed references, and zone "Drawer" has 1 closed reference
- **THEN** "Doors" shows "2 open · 1 closed", "Drawer" shows "0 open · 1 closed" with the hint "Needs an open reference"

#### Scenario: Run setup
- **WHEN** every zone has at least one open and one closed reference and the owner taps "Run setup", and the API answers 200
- **THEN** `POST /api/door-calibration/run` is sent once, the button shows a busy state until the answer, and the new setup state and scores are shown

#### Scenario: Setup fails
- **WHEN** the API answers 422 `{"error": "Doors: open and closed references overlap", "references": [...]}`
- **THEN** that error message is shown, and the scores from the response are shown on the references

#### Scenario: Run setup needs both statuses
- **WHEN** zone "Doors" has an open and a closed reference and zone "Drawer" has only closed ones
- **THEN** "Run setup" is disabled, with the hint "Each zone needs at least one open and one closed reference."

#### Scenario: Stale setup
- **WHEN** `setup.stale` is true
- **THEN** "Zones or references changed. Run setup again." is shown

#### Scenario: Blue light feature named
- **WHEN** the setup has zone "Doors" using `blue` above 0.05 with margin 0.1
- **THEN** the state reads "Doors: Blue light above 5.0%, margin 10.0%"

#### Scenario: Viewer sees setup read-only
- **WHEN** a viewer opens the tab
- **THEN** zones and references are shown with no "Add zone", "Edit", "Delete", "Add reference" or "Run setup" control
