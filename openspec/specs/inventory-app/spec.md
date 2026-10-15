# inventory-app Specification

## Purpose
The phone app for FridgeSense: shows what is in the fridge, what changed at each door opening, how often the fridge is opened, and lets the user confirm what the camera was unsure about.

## Requirements

### Requirement: Sign in with the passcode
The app SHALL show a passcode screen when it has no valid session, keep the session token and its expiry time on the device after signing in, and return to the passcode screen whenever the API answers 401 or the stored expiry time has passed, whether or not the device is online.

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

#### Scenario: Opened after 24 hours
- **WHEN** the app opens and the stored `expires_at` is in the past
- **THEN** the stored token is removed, the passcode screen is shown, and no inventory request is made

#### Scenario: Expires while open
- **WHEN** the app is open on any screen and the clock passes the stored `expires_at`
- **THEN** within 60 seconds the stored token is removed and the passcode screen is shown, even if the device is offline

#### Scenario: Token stored without expiry
- **WHEN** the device has a token from an earlier version of the app but no stored `expires_at`
- **THEN** the token is removed and the passcode screen is shown

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
- **THEN** the screen says the fridge is empty and that items appear after the next door opening or can be added by hand

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
When the session's role is `viewer`, the app SHALL show a "Demo · read-only" badge on every screen, SHALL make Fridge items not editable and hide "Add item", SHALL list pending changes on Review without Confirm, Edit or "Not right" buttons, and SHALL show "Read-only demo" without changing the screen's data if the API answers 403.

#### Scenario: Demo sign-in
- **WHEN** the user signs in with the demo passcode and the API returns `role` `"viewer"`
- **THEN** the token and role are stored, the Fridge screen is shown and a "Demo · read-only" badge is visible

#### Scenario: No edits on Fridge
- **WHEN** the role is `viewer` and the user taps eggs
- **THEN** no item editor opens and no `PUT` or `DELETE` request is sent

#### Scenario: No Add item for viewers
- **WHEN** the role is `viewer`, with items or with an empty fridge
- **THEN** no "Add item" button is shown

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
The app SHALL have a fifth tab, "Ask" (hash `#ask`), with a text box, a send button and five example questions:
- "Do I have milk?"
- "What's in my fridge?"
- "What should I eat first?"
- "What do I need to buy?"
- "When was the fridge last opened?"

Sending a question, or tapping an example, SHALL post it to `/api/ask`. While waiting, the screen shows "Thinking…". The screen then shows the question and the answer, newest first, and reads the answer aloud: it plays the response's `audio` (MP3) when there is one, and otherwise uses speech synthesis when the browser supports it. When `source` is `"agent"` and tools were called, the answer has a small line "Checked: <tool names, comma-separated>". The Ask screen SHALL work the same for owner and viewer roles.

#### Scenario: Typed question
- **WHEN** the user opens `#ask`, types "do I have milk?" and presses send, and the API answers "Yes, you have 1 milk, changed 2 minutes ago." with `audio` `null`
- **THEN** one `ask("do I have milk?")` request is sent, the question and the answer are shown, the text box is cleared, and speech synthesis is asked to speak the answer

#### Scenario: Example question
- **WHEN** the user taps "What's in my fridge?"
- **THEN** that question is posted and its answer is shown

#### Scenario: Five examples
- **WHEN** the user opens `#ask`
- **THEN** the five example questions are shown as buttons in the order above, and tapping "What should I eat first?" posts that question

#### Scenario: Newest first
- **WHEN** the user asks two questions in a row
- **THEN** the second question and its answer appear above the first

#### Scenario: Blank question
- **WHEN** the text box is empty or only spaces and the user presses send
- **THEN** no request is sent

#### Scenario: No speech synthesis
- **WHEN** the browser has no `speechSynthesis`, the response has no `audio`, and a question is answered
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

#### Scenario: Thinking
- **WHEN** a question has been sent and the API has not answered yet
- **THEN** "Thinking…" is shown, and it is gone once the answer appears

#### Scenario: Plays the voice audio
- **WHEN** the API answers with `audio` `"SUQzZmFrZQ=="`
- **THEN** an audio element plays `data:audio/mpeg;base64,SUQzZmFrZQ==` and speech synthesis is not used

#### Scenario: Audio can't play
- **WHEN** the API answers with `audio` but playing it is rejected (for example by the browser's autoplay policy)
- **THEN** speech synthesis is asked to speak the answer instead

#### Scenario: Tools checked
- **WHEN** the API answers with `source` `"agent"` and `data` `{"tools": ["get_inventory", "find_item"]}`
- **THEN** the answer shows "Checked: get_inventory, find_item"

#### Scenario: Keyword answer has no tools line
- **WHEN** the API answers with `source` `"keywords"`
- **THEN** no "Checked:" line is shown

#### Scenario: Leaving stops the voice
- **WHEN** an answer's audio is playing and the user switches to another tab
- **THEN** the audio is paused

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
- **THEN** the screens show their existing empty-list messages ("Your fridge looks empty.", "No door openings on this day.", "Everything is confirmed.", and zeros on Stats), not "No Data"

### Requirement: No error notice for a missing camera
A 409 `{"error": "no camera linked"}` answer SHALL NOT show the "Something went wrong" notice. Other errors keep their existing handling.

#### Scenario: Missing camera is quiet
- **WHEN** polling Fridge answers 409 `{"error": "no camera linked"}` three times in a row
- **THEN** no "Something went wrong" notice is shown

#### Scenario: Other errors still notify
- **WHEN** a request answers 500
- **THEN** the "Something went wrong" notice is shown as before

### Requirement: Config screen
The app SHALL offer a Config screen, opened by a "Config" gear button in the header and reachable at `#config`. It has two sub-sections, "Reference images" and "Custom instructions". For a viewer, both are shown without add, delete or save controls.

#### Scenario: Open config
- **WHEN** the signed-in user taps the gear button
- **THEN** the header title reads "Config", `GET /api/config` is requested, and the "Reference images" and "Custom instructions" sub-sections are shown

#### Scenario: Viewer sees read-only config
- **WHEN** a viewer opens Config and the config has one reference and instructions
- **THEN** the reference thumbnail, its annotation and the instructions are shown, with no "Add", "Delete" or "Save" controls

### Requirement: Manage reference images
The "Reference images" sub-section SHALL list each reference as a thumbnail with its annotation. It SHALL let the owner add one by choosing or taking a photo and typing an annotation, and delete one after confirming. Before upload, the photo SHALL be re-encoded as JPEG with its longer side at most 768 px. The owner SHALL see how many of the 6 are used.

#### Scenario: Add a reference
- **WHEN** the owner taps "Add", picks a 4032×3024 photo, types `soda can` and taps "Save"
- **THEN** `POST /api/config/references` is sent with annotation `soda can` and a JPEG of 768×576, and the list shows the new thumbnail labeled "soda can"

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

### Requirement: Edit custom instructions
The "Custom instructions" sub-section SHALL show the saved instructions in a text area with a live "n / 1000" character count. It SHALL send them only when the owner taps "Save", and confirm with "Saved".

#### Scenario: Save instructions
- **WHEN** the owner types `Count yogurt cups individually.` and taps "Save"
- **THEN** `PUT /api/config/instructions` is sent with `{"instructions": "Count yogurt cups individually."}` and "Saved" is shown

#### Scenario: Over the limit
- **WHEN** the text area holds 1,001 characters
- **THEN** the count reads "1001 / 1000" and "Save" is disabled

#### Scenario: Unchanged text
- **WHEN** the text equals the saved instructions
- **THEN** "Save" is disabled

### Requirement: Door-opening stats
The Stats screen SHALL request the last 28 days of door events and compute everything in the device's time zone. From the last 7 days it SHALL show opens per day as a bar chart with today's bar highlighted, today's number of opens, the number of opens in the last 7 days, and the average time the door stayed open. From all 28 days it SHALL show an "Opens by day and hour" heatmap: 7 rows (Sunday to Saturday) by 24 columns (hours 00–23), each cell shaded in one of 5 levels by how many openings fell in that weekday and hour, with a "Less … More" legend.

#### Scenario: Stats from events
- **WHEN** the last 7 days have 3 openings today (20 s, 30 s and 40 s) and 2 yesterday (25 s and 35 s)
- **THEN** "Today" shows 3, the per-day chart has 7 bars with 3 for today and 2 for yesterday, and the average open time shows "30 s"

#### Scenario: Today marked
- **WHEN** the per-day counts are computed
- **THEN** only the last day (today) has `isToday` true

#### Scenario: Four weeks requested
- **WHEN** the Stats screen loads
- **THEN** it calls `events(28)`

#### Scenario: Older events only in the heatmap
- **WHEN** the events are one opening today and one opening 10 days ago
- **THEN** "Last 7 days" shows 1 and the heatmap counts both openings

#### Scenario: Day and hour heatmap
- **WHEN** there are 2 openings on Mondays at 19:00 and none on Wednesdays at 03:00
- **THEN** the "Opens by day and hour" figure has 168 cells, including "Mon 19:00, 2 opens" and "Wed 03:00, 0 opens", and shows a legend from "Less" to "More"

#### Scenario: Heat levels
- **WHEN** the busiest cell has 8 opens
- **THEN** a cell with 0 opens is level 0, 1 open is level 1, 4 opens is level 2, 5 opens is level 3, and 8 opens is level 4

#### Scenario: Local time zone
- **WHEN** an event opened at 2026-10-15T02:30:00Z (a Thursday in UTC) and the device is in America/Vancouver (UTC−7)
- **THEN** it counts toward Oct 14, hour 19, and the Wednesday row of the heatmap

#### Scenario: No openings yet
- **WHEN** there are no events in the last 28 days
- **THEN** the screen shows zeros, the bar chart shows empty bars, and every heatmap cell is level 0, without errors

### Requirement: Ask screen stops when left
When the user leaves the Ask screen (another tab, or sign-out) while it is listening or reading an answer aloud, the app SHALL stop speech recognition, stop any speech in progress, and send no question from that recognition.

#### Scenario: Leave while listening
- **WHEN** the user taps the mic, switches to the Fridge tab, and recognition then ends with the final transcript "do I have milk"
- **THEN** recognition was stopped when the Ask screen closed and no `ask` request is sent

#### Scenario: Leave while speaking
- **WHEN** an answer is being read aloud and the user switches to another tab
- **THEN** `speechSynthesis.cancel()` is called

### Requirement: Stable still links on Activity
The Activity screen SHALL keep showing the still links it first received for a door event across polls for up to 10 minutes after receiving them, as long as the event still has the same number of stills. After 10 minutes, or when the number of stills changes, it SHALL use the links from the latest poll. A poll that only changes still links SHALL NOT reload the images on screen.

#### Scenario: Poll with fresh links
- **WHEN** Activity shows an event with stills `a1..a4`, and a poll 10 s later returns the same event with new links `b1..b4`
- **THEN** the still images still use `a1..a4`

#### Scenario: Links refreshed after 10 minutes
- **WHEN** a poll more than 10 minutes after `a1..a4` were received returns links `c1..c4`
- **THEN** the still images use `c1..c4`

#### Scenario: Still count changes
- **WHEN** an event shown with 2 stills comes back from a poll with 4 stills
- **THEN** the screen shows the 4 new links

### Requirement: Stale poll responses ignored
A screen that polls SHALL ignore a response from any request that started before a later local change to its data (such as a saved quantity or a confirmed pending change), or before a newer request for the same data. The newest data on screen SHALL never be replaced by older data.

#### Scenario: Poll in flight during a save
- **WHEN** a poll request starts, the user then saves a quantity of 3 for milk, and the poll then returns milk with quantity 2
- **THEN** the screen keeps showing quantity 3 until a poll that started after the save returns

#### Scenario: Out-of-order polls
- **WHEN** poll A starts, poll B starts, B returns, and then A returns with older data
- **THEN** the screen shows B's data

### Requirement: Add an item from the Fridge screen
For the owner, the Fridge screen SHALL show an "Add item" button that opens a sheet with a Name field, a Category picker (default Other) and a Quantity stepper (default 1, minimum 1). Saving SHALL send `POST /api/items`, close the sheet and show the returned list. Save SHALL stay disabled while the name is blank.

#### Scenario: Add butter
- **WHEN** the owner taps "Add item", types "Butter", picks Dairy, sets the quantity to 2 and taps Save
- **THEN** `POST /api/items` is sent with `{"name": "Butter", "category": "dairy", "quantity": 2}`, the sheet closes and the Dairy group shows Butter ×2

#### Scenario: Blank name
- **WHEN** the Add item sheet is open and the name is empty or only spaces
- **THEN** Save is disabled and no request is sent

#### Scenario: Add from an empty fridge
- **WHEN** the owner signs in and there are no items
- **THEN** the empty-fridge message also shows an "Add item" button that opens the Add item sheet

#### Scenario: Add fails
- **WHEN** `POST /api/items` answers 400 `{"error": "unknown category"}`
- **THEN** the sheet stays open, shows "unknown category" and the list is unchanged

### Requirement: Edit or remove an item from the Fridge screen
For the owner, tapping an item SHALL open an editor with its Name, Category and Quantity filled in. Save SHALL send `PUT /api/items/{key}` with `quantity`, plus `name` and `category` only when they changed. "Remove item" SHALL ask "Remove <name>?" first, and only on confirm send `DELETE /api/items/{key}`. Both SHALL show the returned list.

#### Scenario: Rename and recategorize
- **WHEN** the owner taps Bottle (other, ×1), changes the name to "Oat Milk" and the category to Dairy, and saves
- **THEN** `PUT /api/items/bottle` is sent with `{"quantity": 1, "name": "Oat Milk", "category": "dairy"}`, the sheet closes and the Dairy group shows Oat Milk ×1

#### Scenario: Name clash
- **WHEN** the owner renames Bottle to "Oat Milk" and the API answers 409 `{"error": "item exists"}`
- **THEN** the editor stays open and shows "You already have Oat Milk." and the list is unchanged

#### Scenario: Remove an item
- **WHEN** the owner taps Mystery Jar, taps "Remove item" and confirms "Remove Mystery Jar?"
- **THEN** `DELETE /api/items/mystery%20jar` is sent, the sheet closes and Mystery Jar is no longer listed, in stock or under "Out of"

#### Scenario: Remove cancelled
- **WHEN** the owner taps "Remove item" and then cancels the confirmation
- **THEN** no `DELETE` request is sent and the editor is still open
