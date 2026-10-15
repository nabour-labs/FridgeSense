# Spec Delta

## ADDED Requirements

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
- **THEN** the screens show their existing empty-list messages ("Your fridge looks empty.", "No door openings in the last 7 days.", "Everything is confirmed.", and zeros on Stats), not "No Data"

### Requirement: No error notice for a missing camera
A 409 `{"error": "no camera linked"}` answer SHALL NOT show the "Something went wrong" notice. Other errors keep their existing handling.

#### Scenario: Missing camera is quiet
- **WHEN** polling Fridge answers 409 `{"error": "no camera linked"}` three times in a row
- **THEN** no "Something went wrong" notice is shown

#### Scenario: Other errors still notify
- **WHEN** a request answers 500
- **THEN** the "Something went wrong" notice is shown as before
