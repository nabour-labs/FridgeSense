## MODIFIED Requirements

### Requirement: Activity screen
The Activity screen SHALL list door openings newest first with their local time, how long the door was open, the changes as "+ milk", "− 2 eggs" with an arrow showing the direction, a marker on unconfirmed changes, and the stills with the first one shown large. Tapping a still SHALL open it full size in a viewer that can step to the previous and next still. The screen SHALL show one day at a time, today by default, 10 openings per page, and SHALL let the owner delete an opening after confirming.

#### Scenario: Door opening shown
- **WHEN** an event opened at 18:02 local time for 25 s added 1 milk and removed 2 eggs
- **THEN** it shows "18:02", "25 s", "+ milk" and "− 2 eggs"

#### Scenario: Unconfirmed change marked
- **WHEN** an event has a change with `applied = false`
- **THEN** that change shows "to confirm"

#### Scenario: Stills
- **WHEN** an event has 4 still links
- **THEN** 4 still buttons are shown, the first one is marked as the featured still, and tapping one shows it full size

#### Scenario: Step through stills
- **WHEN** the viewer shows still 3 of 4 and the user taps "Next still", then "Previous still" twice
- **THEN** it shows still 4, then still 3, then still 2

#### Scenario: Viewer at the ends
- **WHEN** the viewer shows still 1 of 4
- **THEN** "Previous still" is disabled, and on still 4 of 4 "Next still" is disabled

#### Scenario: No stills
- **WHEN** an event has no still links
- **THEN** no still area is shown for it

#### Scenario: Failed analysis
- **WHEN** an event has `status = "analysis_failed"`
- **THEN** it shows "Couldn't tell what changed" instead of a change list

#### Scenario: No door openings
- **WHEN** there are no events on the chosen day
- **THEN** the screen says there were no door openings on this day, and the day picker stays shown

#### Scenario: Today by default
- **WHEN** the Activity screen opens
- **THEN** the day picker shows today's date, cannot be set past today, and the events requested run from local midnight today to local midnight tomorrow, 10 at a time

#### Scenario: Pick a day
- **WHEN** the user picks yesterday
- **THEN** the events requested run from local midnight yesterday to local midnight today, starting at page 1

#### Scenario: Older and newer pages
- **WHEN** the first page comes back with a `next` id and the user taps "Older"
- **THEN** the next request passes that id as the cursor and the screen shows "Page 2"; tapping "Newer" shows page 1 again

#### Scenario: Single page
- **WHEN** the first page comes back with `next` null
- **THEN** "Older" and "Newer" are both disabled

#### Scenario: Delete an opening
- **WHEN** the owner taps "Delete door opening at 18:02" and then "Delete" in the confirmation
- **THEN** the event is deleted through the API and its card disappears

#### Scenario: Cancel delete
- **WHEN** the owner taps the delete button and then "Cancel"
- **THEN** nothing is deleted and the card stays

#### Scenario: Viewer can't delete
- **WHEN** a viewer opens Activity
- **THEN** no delete button is shown

### Requirement: No Data instead of an endless skeleton
The Fridge, Activity, Review and Stats screens SHALL show a loading skeleton only while their first request is in flight. If that request fails and the screen has no data yet, the screen SHALL show "No Data" in place of the skeleton and keep polling at its usual interval. When a later poll succeeds, the screen SHALL show its normal content. A screen that already shows data SHALL keep showing it when a later poll fails.

#### Scenario: No camera linked
- **WHEN** the user opens Fridge, Activity, Review or Stats and the API answers 409 `{"error": "no camera linked"}`
- **THEN** that screen shows "No Data" and no skeleton is shown

#### Scenario: First load fails
- **WHEN** the first request of a screen answers 500, or fails because the device is offline
- **THEN** the screen shows "No Data" (with the offline banner when offline)

#### Scenario: Still loading
- **WHEN** a screen's first request has not answered yet
- **THEN** the skeleton is shown and "No Data" is not

#### Scenario: Data arrives later
- **WHEN** Fridge shows "No Data" and the next poll 10 s later returns eggs ×6
- **THEN** "No Data" disappears and eggs ×6 is listed

#### Scenario: Later poll fails
- **WHEN** Activity already lists door openings and a later poll answers 500
- **THEN** the door openings stay on screen and "No Data" is not shown

#### Scenario: Empty lists keep their messages
- **WHEN** the API answers 200 with no items, no events or no pending changes
- **THEN** the screens show their existing empty-list messages ("Your fridge looks empty.", "No door openings on this day.", "Everything is confirmed.", and zeros on Stats), not "No Data"
