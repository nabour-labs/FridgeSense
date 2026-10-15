# inventory-app Specification

## Purpose
The phone app for FridgeSense: shows what is in the fridge, what changed at each door opening, how often the fridge is opened, and lets the user confirm what the camera was unsure about.

## Requirements

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
The Fridge screen SHALL show a summary card with the number of in-stock items, when the inventory last changed and, when changes are pending, a link to Review. It SHALL list in-stock items grouped by category with an emoji icon, name, quantity and when each last changed, list items with quantity 0 in a collapsed "Out of" section, and show an illustrated message when the fridge is empty. It SHALL refresh every 10 s while the app is visible.

#### Scenario: Items by category
- **WHEN** the API returns eggs (6, dairy), milk (1, dairy) and apple (3, produce)
- **THEN** the screen shows a "Dairy" group with eggs ×6 and milk ×1 and a "Produce" group with apple ×3

#### Scenario: Out of stock
- **WHEN** soda can has quantity 0
- **THEN** it is not in its category group but appears in the "Out of" section

#### Scenario: Pending banner
- **WHEN** `pending_count` is 2
- **THEN** a link reads "2 items to confirm" and tapping it opens Review

#### Scenario: Summary card
- **WHEN** the API returns eggs (6), milk (1, last changed 2 minutes ago), apple (3) and soda can (0)
- **THEN** a "Fridge summary" region shows "3 in stock" and "Last change 2 min ago"

#### Scenario: Summary with nothing changed yet
- **WHEN** no item has a `last_changed_at`
- **THEN** the summary card shows the in-stock count and no "Last change" text

#### Scenario: Item icons from name
- **WHEN** the items are milk (dairy), apple (produce) and leftover pasta (leftovers)
- **THEN** their rows show 🥛, 🍎 and 🍝

#### Scenario: Item icon falls back to category, then a plate
- **WHEN** the items are kefir (dairy) and mystery jar (other)
- **THEN** kefir shows the dairy icon 🧀 and mystery jar shows 🍽️

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
The Activity screen SHALL list door openings newest first with their local time, how long the door was open, the changes as "+ milk", "− 2 eggs" with an arrow showing the direction, a marker on unconfirmed changes, and the stills with the first one shown large. Tapping a still SHALL open it full size in a viewer that can step to the previous and next still.

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
- **WHEN** there are no events in the last 7 days
- **THEN** the screen says there were no door openings in the last 7 days

### Requirement: Review screen
The Review screen SHALL list pending changes with the item, direction, quantity and confidence as a percentage and as a meter coloured by confidence, and let the user confirm, edit then confirm, or reject each one.

#### Scenario: Confirm
- **WHEN** the user taps "Confirm" on a pending "− chocolate bar" at 62%
- **THEN** `POST /api/pending/{id}/confirm` is sent and the change disappears from the list

#### Scenario: Confidence meter
- **WHEN** pending changes have confidence 0.62, 0.48 and 0.85
- **THEN** each card has a "Confidence" meter with value 62, 48 and 85, toned "medium", "low" and "high"

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
The Stats screen SHALL show, from the last 7 days of door events in the device's time zone: opens per day as a bar chart with today's bar highlighted, opens by hour of day as a 24-cell heat strip, today's number of opens, and the average time the door stayed open.

#### Scenario: Stats from events
- **WHEN** the last 7 days have 3 openings today (20 s, 30 s and 40 s) and 2 yesterday (25 s and 35 s)
- **THEN** "Today" shows 3, the per-day chart has 7 bars with 3 for today and 2 for yesterday, and the average open time shows "30 s"

#### Scenario: Today marked
- **WHEN** the per-day counts are computed
- **THEN** only the last day (today) has `isToday` true

#### Scenario: Hour heat strip
- **WHEN** there are 2 openings at 19:00 and none at 03:00
- **THEN** the "Opens by hour" figure has 24 cells, labelled "19:00, 2 opens" and "03:00, 0 opens"

#### Scenario: Local time zone
- **WHEN** an event opened at 2026-10-15T02:30:00Z and the device is in America/Vancouver (UTC−7)
- **THEN** it counts toward Oct 14 and hour 19

#### Scenario: No openings yet
- **WHEN** there are no events in the last 7 days
- **THEN** the screen shows zeros and the charts show empty bars, without errors

### Requirement: Installable app
The app SHALL ship a web app manifest (name "FridgeSense", standalone display, icons of 192 and 512 px, theme colours that match the brand theme) and a service worker that serves the app shell offline. It SHALL set `theme-color` separately for light and dark mode, SHALL ship iOS splash images for common iPhone sizes, and SHALL fit phone screens from 360 px wide without horizontal scrolling.

#### Scenario: Manifest
- **WHEN** the built app is inspected
- **THEN** `manifest.webmanifest` has `name` "FridgeSense", `display` "standalone" and icons sized 192x192 and 512x512

#### Scenario: Theme colour per scheme
- **WHEN** `index.html` is inspected
- **THEN** it has a `theme-color` meta for `(prefers-color-scheme: light)` and one for `(prefers-color-scheme: dark)`

#### Scenario: iOS splash images
- **WHEN** `index.html` is inspected
- **THEN** every `apple-touch-startup-image` link points to a file that exists under `public/`, and there are at least 3

#### Scenario: Offline shell
- **WHEN** the installed app is opened without a network
- **THEN** the app shell loads and shows that it can't reach FridgeSense, instead of a browser error page

### Requirement: Read-only demo mode
When the session's role is `viewer`, the app SHALL show a "Demo · read-only" badge on every screen, SHALL make Fridge items not editable, SHALL list pending changes on Review without Confirm, Edit or "Not right" buttons, and SHALL show "Read-only demo" without changing the screen's data if the API answers 403.

#### Scenario: Demo sign-in
- **WHEN** the user signs in with the demo passcode and the API returns `role` `"viewer"`
- **THEN** the token and role are stored, the Fridge screen is shown and a "Demo · read-only" badge is visible

#### Scenario: No edits on Fridge
- **WHEN** the role is `viewer` and the user taps eggs
- **THEN** no quantity editor opens and no `PUT` request is sent

#### Scenario: No actions on Review
- **WHEN** the role is `viewer` and one change is pending
- **THEN** Review lists it with item, direction, quantity and confidence, and shows no Confirm, Edit or "Not right" buttons

#### Scenario: Write refused
- **WHEN** a write request answers 403
- **THEN** the app shows "Read-only demo" and the list on screen is unchanged

### Requirement: Visual style
The app SHALL define its colours as Tailwind theme tokens (`--color-brand-*` for the teal accent, `--color-warm-*` for the amber accent), SHALL use the bundled Plus Jakarta Sans font so text looks the same offline, and SHALL turn off its animations and transitions when the device asks for reduced motion.

#### Scenario: Theme tokens
- **WHEN** `src/index.css` is inspected
- **THEN** it defines `--color-brand-500` and `--color-warm-500` in a `@theme` block and imports `@fontsource-variable/plus-jakarta-sans`

#### Scenario: Font cached offline
- **WHEN** the service worker precache patterns are inspected
- **THEN** they include `woff2` files

#### Scenario: Reduced motion
- **WHEN** `src/index.css` is inspected
- **THEN** a `@media (prefers-reduced-motion: reduce)` rule sets animation and transition durations to near zero

### Requirement: Ask screen
The app SHALL have a fifth tab, "Ask" (hash `#ask`), with a text box, a send button and three example questions:
- "Do I have milk?"
- "What's in my fridge?"
- "When was the fridge last opened?"

Sending a question, or tapping an example, SHALL post it to `/api/ask`. The screen then shows the question and the answer, newest first, and reads the answer aloud when the browser supports speech synthesis. The Ask screen SHALL work the same for owner and viewer roles.

#### Scenario: Typed question
- **WHEN** the user opens `#ask`, types "do I have milk?" and presses send, and the API answers "Yes, you have 1 milk, changed 2 minutes ago."
- **THEN** one `ask("do I have milk?")` request is sent, the question and the answer are shown, the text box is cleared, and speech synthesis is asked to speak the answer

#### Scenario: Example question
- **WHEN** the user taps "What's in my fridge?"
- **THEN** that question is posted and its answer is shown

#### Scenario: Newest first
- **WHEN** the user asks two questions in a row
- **THEN** the second question and its answer appear above the first

#### Scenario: Blank question
- **WHEN** the text box is empty or only spaces and the user presses send
- **THEN** no request is sent

#### Scenario: No speech synthesis
- **WHEN** the browser has no `speechSynthesis` and a question is answered
- **THEN** the answer is shown and no error appears

#### Scenario: Viewer asks
- **WHEN** the role is `viewer` and the user asks "Do I have milk?"
- **THEN** the answer is shown and no "Read-only demo" notice appears

#### Scenario: Request fails
- **WHEN** the ask request fails because FridgeSense can't be reached
- **THEN** the app shows its offline banner, the question stays in the text box, and no answer is added

#### Scenario: Five tabs
- **WHEN** the signed-in app is shown
- **THEN** the bottom navigation has Fridge, Activity, Review, Stats and Ask, and opening `#ask` shows the Ask screen with the title "Ask"

### Requirement: Speak a question
When the browser supports speech recognition (`SpeechRecognition` or `webkitSpeechRecognition`), the Ask screen SHALL show a mic button. Tapping it starts listening in English (`en-US`), with a visible "Listening…" state. The first final transcript SHALL be posted as the question. Tapping the button again while listening SHALL stop listening without sending anything. Without speech recognition, the mic button SHALL NOT be shown.

#### Scenario: Spoken question
- **WHEN** speech recognition is available, the user taps the mic, and recognition returns the final transcript "do I have milk"
- **THEN** "Listening…" is shown while recognition runs, `ask("do I have milk")` is sent once, and its answer is shown and spoken

#### Scenario: No speech recognition
- **WHEN** neither `SpeechRecognition` nor `webkitSpeechRecognition` exists
- **THEN** no mic button is shown and the text box still works

#### Scenario: Nothing heard
- **WHEN** recognition ends with an error (`no-speech`, `not-allowed` or `aborted`), or ends with no final transcript
- **THEN** the screen shows "Didn't catch that. Try again or type your question.", leaves "Listening…", and sends no request

#### Scenario: Stop listening
- **WHEN** the user taps the mic while it is listening
- **THEN** recognition is stopped and no request is sent

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
