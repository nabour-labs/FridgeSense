## MODIFIED Requirements

### Requirement: Open/close detection tab
The "Open/close detection" tab SHALL list the door references as thumbnails, each with its box drawn on it, an "Open" or "Closed" badge, and its score as a percentage with one decimal (or "–" when it has none), oldest first, with "n of 12" shown. The owner SHALL be able to add a reference: tapping "Add" requests a camera snapshot, the owner drags on it to draw one box (a new drag replaces the box), picks "Open" or "Closed", and taps "Save" to send `POST /api/door-calibration/references`. The owner SHALL be able to delete a reference after confirming. A "Run setup" button SHALL send `POST /api/door-calibration/run`. It is enabled only when there is at least one open and one closed reference. The tab SHALL show the setup state:
- "Not set up yet. Using default zones." when `setup` is null.
- One line per setup zone when `setup` exists: "Zone n: <Blue light | Color | Brightness | Change> above (or below) t%, margin m%".
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

#### Scenario: Blue light feature named
- **WHEN** the setup has one zone using `blue` above 0.05 with margin 0.1
- **THEN** the state reads "Zone 1: Blue light above 5.0%, margin 10.0%"
