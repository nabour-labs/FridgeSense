## MODIFIED Requirements

### Requirement: Activity screen
The Activity screen SHALL list door openings newest first with their local time, how long the door was open, the changes as "+ milk", "− 2 eggs" with an arrow showing the direction, and a marker on unconfirmed changes. When an event has a `clip` link, the card SHALL show that clip instead of its stills: an inline video, muted, with controls, that plays inline and does not autoplay, with the first still as its poster. Otherwise it SHALL show the stills with the first one shown large, and tapping a still SHALL open it full size in a viewer that can step to the previous and next still. The screen SHALL show one day at a time, by default today or, when today has no openings, the most recent day in the last 31 days that has one, 10 openings per page, and SHALL let the owner delete an opening after confirming.

#### Scenario: Door opening shown
- **WHEN** an event opened at 18:02 local time for 25 s added 1 milk and removed 2 eggs
- **THEN** it shows "18:02", "25 s", "+ milk" and "− 2 eggs"

#### Scenario: Unconfirmed change marked
- **WHEN** an event has a change with `applied = false`
- **THEN** that change shows "to confirm"

#### Scenario: Clip instead of stills
- **WHEN** an event has a `clip` link ending in `#t=0.5,8.5` and 4 still links
- **THEN** the card shows one video labelled "Door opening at <time>" whose source is that link, which is muted, has controls, plays inline, does not autoplay and uses the first still as its poster, and no still buttons are shown

#### Scenario: Clip without stills
- **WHEN** an event has a `clip` link and no still links
- **THEN** the video is shown with no poster

#### Scenario: Clip fails to load
- **WHEN** the clip video fires an `error` event and the event has 4 still links
- **THEN** the card shows the 4 still buttons in place of the video

#### Scenario: Stills
- **WHEN** an event has `clip: null` and 4 still links
- **THEN** 4 still buttons are shown, the first one is marked as the featured still, and tapping one shows it full size

#### Scenario: Step through stills
- **WHEN** the viewer shows still 3 of 4 and the user taps "Next still", then "Previous still" twice
- **THEN** it shows still 4, then still 3, then still 2

#### Scenario: Viewer at the ends
- **WHEN** the viewer shows still 1 of 4
- **THEN** "Previous still" is disabled, and on still 4 of 4 "Next still" is disabled

#### Scenario: No stills
- **WHEN** an event has no still links and `clip: null`
- **THEN** no still or clip area is shown for it

#### Scenario: Failed analysis
- **WHEN** an event has `status = "analysis_failed"`
- **THEN** it shows "Couldn't tell what changed" instead of a change list

#### Scenario: No door openings
- **WHEN** there are no events on the chosen day
- **THEN** the screen says there were no door openings on this day, and the day picker stays shown

#### Scenario: Today by default
- **WHEN** the Activity screen opens and today has door openings
- **THEN** the day picker shows today's date, cannot be set past today, and the events requested run from local midnight today to local midnight tomorrow, 10 at a time

#### Scenario: Last day with openings by default
- **WHEN** the Activity screen opens, today has no door openings, and the newest opening in the last 31 days was 3 days ago
- **THEN** the day picker shows the date 3 days ago and the events requested run from local midnight that day to local midnight the next day, 10 at a time

#### Scenario: No openings in the last 31 days
- **WHEN** the Activity screen opens and there are no door openings in the last 31 days, or looking them up fails
- **THEN** the day picker shows today's date

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
