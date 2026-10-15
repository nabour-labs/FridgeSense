# Spec Delta

## Purpose

The phone app for FridgeSense: shows what is in the fridge, what changed at each door opening, how often the fridge is opened, and lets the user confirm what the camera was unsure about.

## ADDED Requirements

### Requirement: Sign in with the passcode
The app SHALL show a passcode screen when it has no valid session, keep the session token on the device after signing in, and return to the passcode screen whenever the API answers 401.

#### Scenario: First visit
- **WHEN** the app opens with no stored token
- **THEN** it shows a passcode field and a "Sign in" button, and no inventory request is made

#### Scenario: Successful sign-in
- **WHEN** the user enters the correct passcode and taps "Sign in"
- **THEN** the token is stored and the Fridge screen is shown

#### Scenario: Wrong passcode
- **WHEN** the API answers 401 to the sign-in
- **THEN** the app shows "Wrong passcode" and stays on the passcode screen

#### Scenario: Session expired
- **WHEN** any API call answers 401 while signed in
- **THEN** the stored token is removed and the passcode screen is shown

### Requirement: Fridge screen
The Fridge screen SHALL list in-stock items grouped by category with name, quantity and when each last changed, list items with quantity 0 in a collapsed "Out of" section, and show a banner linking to Review when changes are pending. It SHALL refresh every 10 s while the app is visible.

#### Scenario: Items by category
- **WHEN** the API returns eggs (6, dairy), milk (1, dairy) and apple (3, produce)
- **THEN** the screen shows a "Dairy" group with eggs ×6 and milk ×1 and a "Produce" group with apple ×3

#### Scenario: Out of stock
- **WHEN** soda can has quantity 0
- **THEN** it is not in its category group but appears in the "Out of" section

#### Scenario: Pending banner
- **WHEN** `pending_count` is 2
- **THEN** a banner reads "2 items to confirm" and tapping it opens Review

#### Scenario: Empty fridge
- **WHEN** there are no items
- **THEN** the screen says the fridge is empty and that items appear after the next door opening

#### Scenario: Live refresh
- **WHEN** the app is visible and 10 s pass
- **THEN** the inventory is requested again and new quantities are shown without a reload

#### Scenario: Hidden app does not poll
- **WHEN** the page is hidden
- **THEN** no further inventory requests are made until it is visible again

#### Scenario: Fix a quantity
- **WHEN** the user taps an item, changes eggs from 6 to 12 and saves
- **THEN** `PUT /api/items/eggs` is sent with `{"quantity": 12}` and the list shows eggs ×12

### Requirement: Activity screen
The Activity screen SHALL list door openings newest first with their local time, how long the door was open, the changes as "+ milk", "− 2 eggs", a marker on unconfirmed changes, and thumbnails of the stills that open full size when tapped.

#### Scenario: Door opening shown
- **WHEN** an event opened at 18:02 local time for 25 s added 1 milk and removed 2 eggs
- **THEN** it shows "18:02", "25 s", "+ milk" and "− 2 eggs"

#### Scenario: Stills
- **WHEN** an event has 4 still links
- **THEN** 4 thumbnails are shown, and tapping one shows it full size

#### Scenario: Failed analysis
- **WHEN** an event has `status = "analysis_failed"`
- **THEN** it shows "Couldn't tell what changed" instead of a change list

### Requirement: Review screen
The Review screen SHALL list pending changes with the item, direction, quantity and confidence as a percentage, and let the user confirm, edit then confirm, or reject each one.

#### Scenario: Confirm
- **WHEN** the user taps "Confirm" on a pending "− chocolate bar" at 62%
- **THEN** `POST /api/pending/{id}/confirm` is sent and the change disappears from the list

#### Scenario: Edit and confirm
- **WHEN** the user taps "Edit" on "+ bottle", changes the name to "Oat Milk" and quantity to 2, and confirms
- **THEN** the confirm request body is `{"item": "Oat Milk", "quantity": 2}`

#### Scenario: Reject
- **WHEN** the user taps "Not right"
- **THEN** `POST /api/pending/{id}/reject` is sent and the change disappears from the list

#### Scenario: Nothing to review
- **WHEN** there are no pending changes
- **THEN** the screen says everything is confirmed

### Requirement: Stats screen
The Stats screen SHALL show, from the last 7 days of door events in the device's time zone: opens per day as a bar chart, opens by hour of day as a bar chart, today's number of opens, and the average time the door stayed open.

#### Scenario: Stats from events
- **WHEN** the last 7 days have 3 openings today (20 s, 30 s and 40 s) and 2 yesterday (25 s and 35 s)
- **THEN** "Today" shows 3, the per-day chart has 7 bars with 3 for today and 2 for yesterday, and the average open time shows "30 s"

#### Scenario: Local time zone
- **WHEN** an event opened at 2026-10-15T02:30:00Z and the device is in America/Vancouver (UTC−7)
- **THEN** it counts toward Oct 14 and hour 19

#### Scenario: No openings yet
- **WHEN** there are no events in the last 7 days
- **THEN** the screen shows zeros and the charts show empty bars, without errors

### Requirement: Installable app
The app SHALL ship a web app manifest (name "FridgeSense", standalone display, icons of 192 and 512 px) and a service worker that serves the app shell offline, and SHALL fit phone screens from 360 px wide without horizontal scrolling.

#### Scenario: Manifest
- **WHEN** the built app is inspected
- **THEN** `manifest.webmanifest` has `name` "FridgeSense", `display` "standalone" and icons sized 192x192 and 512x512

#### Scenario: Offline shell
- **WHEN** the installed app is opened without a network
- **THEN** the app shell loads and shows that it can't reach FridgeSense, instead of a browser error page
