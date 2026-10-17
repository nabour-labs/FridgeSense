# Spec Delta

## MODIFIED Requirements

### Requirement: Activity screen
The Activity screen SHALL list door openings newest first with their local time, how long the door was open, the changes as "+ milk", "− 2 eggs" with an arrow showing the direction, and a marker on unconfirmed changes. When an event has a `clip` link, the card SHALL show that clip instead of its stills: an inline video, muted, with controls, that plays inline and does not autoplay, with the first still as its poster. Otherwise it SHALL show the stills with the first one shown large, and tapping a still SHALL open it full size in a viewer that can step to the previous and next still. The screen SHALL show one day at a time, today by default, 10 openings per page, and SHALL let the owner delete an opening after confirming.

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

### Requirement: Stable still links on Activity
The Activity screen SHALL keep showing the still links and the clip link it first received for a door event across polls for up to 10 minutes after receiving them, as long as the event still has the same number of stills and still has (or still lacks) a clip. After 10 minutes, or when either changes, it SHALL use the links from the latest poll. A poll that only changes links SHALL NOT reload the images or the clip on screen.

#### Scenario: Poll with fresh links
- **WHEN** Activity shows an event with stills `a1..a4`, and a poll 10 s later returns the same event with new links `b1..b4`
- **THEN** the still images still use `a1..a4`

#### Scenario: Poll with a fresh clip link
- **WHEN** Activity shows an event with clip link `v1`, and a poll 10 s later returns the same event with clip link `v2`
- **THEN** the video still uses `v1` and is not reloaded

#### Scenario: Links refreshed after 10 minutes
- **WHEN** a poll more than 10 minutes after `a1..a4` were received returns links `c1..c4`
- **THEN** the still images use `c1..c4`

#### Scenario: Still count changes
- **WHEN** an event shown with 2 stills comes back from a poll with 4 stills
- **THEN** the screen shows the 4 new links

#### Scenario: Clip appears
- **WHEN** an event shown with `clip: null` comes back from a poll with clip link `v1`
- **THEN** the card shows the video with `v1`
