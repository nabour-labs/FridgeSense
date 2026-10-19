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
The "Reference images" sub-section SHALL list each reference as a thumbnail with its annotation (its description). It SHALL let the owner add one and delete one after confirming. Adding SHALL offer three sources: "Choose photo" (pick or take a photo on the device), "Camera snapshot" (`POST /api/camera/snapshot`) and "Recent clip". "Recent clip" SHALL open the "Snapshot from a recent clip" sheet: a dropdown of the door openings from the last 7 days that have a `clip`, newest first, each labelled with its day, local time and duration (e.g. "Today 18:02 · 25 s"); the selected clip plays with a scrubber; "Use this frame" sends the shown frame, as a JPEG at most 960 px wide, to `POST /api/camera/frame`, and only the image that route returns is shown for drawing; "Cancel" closes the sheet without a request. Once an image is chosen, the owner SHALL be able to drag boxes on it, undo the last box with "Undo", and type the annotation, up to 300 characters, in a multi-line field. There SHALL be no "Box" or "Line" tool buttons and no way to draw a line. Once at least one box is drawn, a "Crop" button SHALL crop the image to the last box, taken from the full-resolution image; the cropped image SHALL replace the one shown and its boxes SHALL be cleared. "Undo" with no boxes left after a crop SHALL restore the image from before that crop, with its boxes. The boxes SHALL be drawn in red into the uploaded image. Before upload, the image SHALL be re-encoded as JPEG with its longer side at most 768 px. The owner SHALL see how many of the 6 are used.

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
- **WHEN** the owner drags from 10%, 10% to 40%, 50% of the image, then from 50%, 50% to 90%, 90%, and taps "Save"
- **THEN** there are no "Box" or "Line" buttons, and the shapes passed to the upload are a box from `(0.1, 0.1)` to `(0.4, 0.5)` and a box from `(0.5, 0.5)` to `(0.9, 0.9)`, in that order, drawn in red into the JPEG

#### Scenario: Crop to the box
- **WHEN** the owner draws a box from 10%, 10% to 40%, 50% on a 1000×800 image and taps "Crop"
- **THEN** the image is cropped to the 300×320 px region at (100, 80), the cropped image is shown for drawing with no boxes, and after typing `milk bag` and tapping "Save" the cropped image (not the original) is uploaded, with no shapes

#### Scenario: Crop needs a box
- **WHEN** an image is chosen and no box is drawn
- **THEN** "Crop" is disabled

#### Scenario: Undo a crop
- **WHEN** the owner draws a box, taps "Crop", then taps "Undo"
- **THEN** the original image is shown again with that box, and "Crop" is enabled

#### Scenario: Undo a shape
- **WHEN** the owner has drawn two shapes and taps "Undo"
- **THEN** only the first shape remains, and "Undo" is disabled when no shapes are left

#### Scenario: Annotation required
- **WHEN** the owner picks a photo but leaves the annotation empty
- **THEN** "Save" is disabled and no request is sent

#### Scenario: Long annotation
- **WHEN** the owner types a 300-character annotation and then one more character
- **THEN** the field holds the 300 characters and "Save" sends all of them

#### Scenario: Limit reached
- **WHEN** 6 references exist
- **THEN** the sub-section shows "6 of 6" and the "Add" button is disabled

#### Scenario: Delete a reference
- **WHEN** the owner taps "Delete" on "milk bag" and confirms
- **THEN** `DELETE /api/config/references/{id}` is sent and "milk bag" disappears from the list

#### Scenario: Upload refused
- **WHEN** the API answers 400 or 409 to an add
- **THEN** the error message from the response is shown and the list is unchanged

#### Scenario: Add a reference from a recent clip
- **WHEN** the owner taps "Add", then "Recent clip", picks the 18:02 opening, taps "Use this frame", and `POST /api/camera/frame` answers 200 with a 960×540 image
- **THEN** the grabbed frame was sent to `POST /api/camera/frame`, the returned image is shown for drawing, and after typing `milk bag` and tapping "Save", the uploaded JPEG is 768×432

#### Scenario: Recent clips listed
- **WHEN** the last 7 days hold openings today at 18:02 (25 s, with a clip), today at 09:15 (no clip) and yesterday at 20:40 (12 s, with a clip)
- **THEN** the dropdown lists "Today 18:02 · 25 s" then "Yesterday 20:40 · 12 s", the first is selected, and its video plays the clip link with `crossOrigin` set to `anonymous`

#### Scenario: No recent clips
- **WHEN** no door opening in the last 7 days has a clip
- **THEN** the sheet says "No door openings with a clip in the last 7 days." and "Use this frame" is disabled

#### Scenario: Recent clip won't load
- **WHEN** the selected clip fails to load
- **THEN** the sheet says "This clip can't be played" and "Use this frame" is disabled

#### Scenario: Frame can't be grabbed
- **WHEN** drawing the frame fails
- **THEN** the sheet says "This frame can't be used. Try another clip." and no request is sent

#### Scenario: Faces can't be blurred
- **WHEN** `POST /api/camera/frame` answers 502
- **THEN** the sheet says "Faces couldn't be blurred, so this frame can't be used." and no image is shown for drawing

#### Scenario: Cancel the recent clip picker
- **WHEN** the owner taps "Cancel" in the sheet
- **THEN** the sheet closes, no image is shown for drawing, and `POST /api/camera/frame` is not requested

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

### Requirement: Daily open-time stats
The Stats screen SHALL show an "Open time" card with the average, longest and shortest `duration_s` of the door events that opened on one selected local day (device time zone). The card SHALL offer one button for each of the last 7 days, oldest first, labelled with the short weekday except the last, which is labelled "Today"; the selected button SHALL be marked pressed, and today SHALL be selected when the screen opens. The average SHALL be rounded to the nearest whole second. Each value SHALL read "N s" below 60 seconds and "M m SS s" from 60 seconds up, with seconds padded to 2 digits. A day with no openings SHALL show "–" for all three values and the text "No openings".

#### Scenario: Today's open times
- **WHEN** today has 3 openings of 20 s, 30 s and 40 s and yesterday has 2 openings of 25 s and 35 s
- **THEN** the "Open time" card has "Today" pressed and shows Average "30 s", Longest "40 s" and Shortest "20 s"

#### Scenario: Pick another day
- **WHEN** the user taps the button for yesterday in the same data
- **THEN** that button is pressed, "Today" is not, and the card shows Average "30 s", Longest "35 s" and Shortest "25 s"

#### Scenario: Seven day buttons
- **WHEN** the Stats screen loads
- **THEN** the "Open time" card has 7 day buttons for the last 7 local days, oldest first, the last one labelled "Today"

#### Scenario: Minutes and seconds
- **WHEN** durations are formatted
- **THEN** 0 reads "0 s", 45 reads "45 s", 59 reads "59 s", 60 reads "1 m 00 s", 65 reads "1 m 05 s" and 600 reads "10 m 00 s"

#### Scenario: Long opening on the card
- **WHEN** today has openings of 65 s and 20 s
- **THEN** the card shows Longest "1 m 05 s", Shortest "20 s" and Average "43 s"

#### Scenario: Average rounded
- **WHEN** a day has openings of 20 s and 25 s
- **THEN** the average is 23 s

#### Scenario: Single opening
- **WHEN** a day has one opening of 18 s
- **THEN** Average, Longest and Shortest all show "18 s"

#### Scenario: Day without openings
- **WHEN** the selected day has no openings
- **THEN** Average, Longest and Shortest each show "–" and the card shows "No openings", without errors

#### Scenario: Open time in local days
- **WHEN** an event opened at 2026-10-15T02:30:00Z with `duration_s` 50 and the device is in America/Vancouver (UTC−7)
- **THEN** it counts toward the Oct 14 open-time stats and not Oct 15

### Requirement: Sign out
While signed in with any role, the app SHALL show a "Sign out" button in the header on every screen. Tapping it SHALL remove the stored token, role and expiry and show the passcode screen, without an API call.

#### Scenario: Sign out
- **WHEN** the user is signed in on the Fridge screen and taps "Sign out"
- **THEN** the passcode screen is shown, `fridgesense.token`, `fridgesense.role` and `fridgesense.expires` are no longer in storage, and no request is sent

#### Scenario: Signed out stays signed out
- **WHEN** the user taps "Sign out" and the app is reloaded
- **THEN** the passcode screen is shown and no inventory request is made

### Requirement: Admin-only Debug for the user role
When the session's role is `user`, the app SHALL behave as for the owner (editable Fridge items, "Add item", Review actions, Config add, delete, run, set and save controls), except that it SHALL NOT show the "Debug" Config tab or the "Debug" links on Activity cards, SHALL show no "Demo · read-only" badge, and opening `#config/debug` SHALL show the "Reference images" tab.

#### Scenario: User sign-in
- **WHEN** the user signs in and the API returns `role` `"user"`
- **THEN** the role `user` is stored, the Fridge screen is shown, no "Demo · read-only" badge is visible and "Add item" is shown

#### Scenario: User sees no Debug tab
- **WHEN** the role is `user` and the user opens Config
- **THEN** the "Reference images", "Open/close detection" and "Fridge area" tabs are shown, with "Add" controls, and no "Debug" tab

#### Scenario: User opens the debug hash
- **WHEN** the role is `user` and the app opens at `#config/debug`
- **THEN** the "Reference images" tab is shown and no `/api/debug` request is made

#### Scenario: No Debug link for users
- **WHEN** the role is `user` and Activity lists a door opening
- **THEN** the card has a delete control and no "Debug" link

#### Scenario: User role restored
- **WHEN** the app opens with a stored, unexpired session whose role is `user`
- **THEN** the role is `user` (no "Debug" tab in Config)

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

### Requirement: Fridge area tab
The "Fridge area" tab SHALL show the saved fridge area as its snapshot with the box drawn on it and "Saved <date and time>", or "No fridge area yet." when `area` is null. The owner SHALL be able to set the area: tapping "Set area" (or "Change area" when one is saved) requests a camera snapshot, the owner drags on it to draw one box around the fridge (a new drag replaces the box), and taps "Save" to send `PUT /api/fridge-area` with the snapshot image and the box. "Cancel" SHALL close the editor without a request. A viewer SHALL see the saved area with no "Set area", "Change area" or "Save" control.

#### Scenario: Fridge area shown
- **WHEN** the tab loads an area with box `{"x": 0.2, "y": 0.05, "width": 0.5, "height": 0.9}`
- **THEN** the snapshot is shown with one box covering 20%–70% across and 5%–95% down, and the button reads "Change area"

#### Scenario: No fridge area
- **WHEN** the tab loads with `area = null`
- **THEN** "No fridge area yet." is shown and the button reads "Set area"

#### Scenario: Set the fridge area
- **WHEN** the owner taps "Set area", the snapshot answers 200, the owner drags from 20%, 5% to 70%, 95% of the image and taps "Save"
- **THEN** `PUT /api/fridge-area` is sent with the snapshot image and box `{"x": 0.2, "y": 0.05, "width": 0.5, "height": 0.9}`, and the tab shows the saved area

#### Scenario: Box required to save
- **WHEN** the snapshot is shown and no box is drawn
- **THEN** "Save" is disabled and no request is sent

#### Scenario: Redraw replaces the fridge box
- **WHEN** the owner draws one box and then drags again elsewhere
- **THEN** only the second box is shown and sent

#### Scenario: Cancel setting the area
- **WHEN** the owner taps "Set area", draws a box and taps "Cancel"
- **THEN** no `PUT /api/fridge-area` is sent and the saved area (or "No fridge area yet.") is shown again

#### Scenario: Snapshot fails while setting the area
- **WHEN** the API answers 409 `{"error": "no recent footage"}` to the snapshot
- **THEN** "No recent footage. Walk past the camera, then try again." is shown with a "Try again" button that requests a new snapshot

#### Scenario: Viewer sees the fridge area read-only
- **WHEN** a viewer opens the tab and an area is saved
- **THEN** the snapshot and box are shown, with no "Set area", "Change area" or "Save" control

### Requirement: Debug motion list
The "Debug" tab SHALL list traced motions for one day (today by default, with the same day picker and "Older"/"Newer" paging as Activity). Each row shows the local time, the outcome ("Door opening", "Not the door", "No stills", "Duplicate"), the best score against its threshold, and for door openings the Nova call count, total input and output tokens, cost in USD and total latency. Tapping a row SHALL open `#config/debug/<id>`.

#### Scenario: Not-door row
- **WHEN** a motion at 18:02 has `outcome = "not_door"` and `best = {value: 0.0123, threshold: 0.02}`
- **THEN** its row shows "18:02", "Not the door" and "0.0123 / 0.02", and no Nova figures

#### Scenario: Door opening row
- **WHEN** a door opening has `nova = {calls: 2, input_tokens: 2380, output_tokens: 186, usd: 0.00162, latency_ms: 4040}`
- **THEN** its row shows "2 calls", "2,380 in", "186 out", "$0.0016" and "4.0 s"

#### Scenario: No motions
- **WHEN** no motions were traced on the chosen day
- **THEN** the tab says no motions were recorded on this day

#### Scenario: Open a motion
- **WHEN** the owner taps a row with id `abc`
- **THEN** the hash becomes `#config/debug/abc` and `GET /api/debug/motions/abc` is requested

### Requirement: Debug motion detail
The detail view at `#config/debug/<id>` SHALL show the door section, then one section per Nova call, with a "Back" control to the list. The door section shows every raw still with its time, open/closed verdict and each zone's value against its threshold, with the zone boxes drawn on it. It also shows the rule source, each zone's feature, direction, threshold, margin and baseline, and the door reference images with their status.

#### Scenario: Door section
- **WHEN** a trace has 6 stills, stills 3–4 open, setup rule with 1 `change` zone (threshold 0.11, margin 0.07) and 3 references
- **THEN** 6 still images are shown in order, stills 3 and 4 are marked "Open" and the rest "Closed", each shows its zone 1 value against 0.11, the zone row shows "change", "above", "0.11" and margin "0.07" with its baseline image, and 3 reference images are shown with "open" or "closed"

#### Scenario: Picked stills marked
- **WHEN** stills 3 and 4 were picked for analysis
- **THEN** those two raw stills are marked "Sent to analysis"

#### Scenario: Missing still
- **WHEN** still 5 has `url = null` and `missing_status = 416`
- **THEN** a placeholder reading "Not downloaded (416)" is shown in its place

#### Scenario: Default rule
- **WHEN** the trace's `rule.source = "default"`
- **THEN** the rule is labelled "Default zones" and no baseline or reference images are shown

#### Scenario: Missing detail
- **WHEN** `GET /api/debug/motions/<id>` answers 404
- **THEN** the view says the trace has expired or was never recorded, and "Back" returns to the list

### Requirement: Nova call detail
Each Nova call section SHALL show, in request order, every text block as text and every image (references and stills) as a thumbnail labelled with its role and number, which opens full size when tapped. It then shows the response as formatted JSON with the stop reason, and input, output, cache-read and cache-write tokens, cost, Bedrock latency and wall time.

#### Scenario: Request in order
- **WHEN** a call sent 2 references and 4 stills
- **THEN** the section shows the reference header, "Reference 1: …", reference thumbnail 1, "Reference 2: …", reference thumbnail 2, "Image 1 of 4", still thumbnail 1 … still thumbnail 4, then the instruction text

#### Scenario: Numbers shown
- **WHEN** a call has 1180 input, 96 output, 2000 cache-read and 0 cache-write tokens, `usd = 0.000818`, `latency_ms = 2140` and `wall_ms = 2310`
- **THEN** the section shows "1,180", "96", "2,000", "0", "$0.000818", "2.14 s" and "2.31 s"

#### Scenario: Failed call
- **WHEN** a call has `outcome = "error"` and `error_code = "ThrottlingException"`
- **THEN** the section shows "ThrottlingException" in place of the response and no token figures

#### Scenario: Invalid answer
- **WHEN** a call has `outcome = "invalid"` and `response.stopReason = "end_turn"`
- **THEN** the section is marked "Invalid answer" and shows the response JSON with stop reason "end_turn"

### Requirement: Debug link on Activity
On the Activity screen, each door opening card SHALL show a "Debug" link for the owner that opens `#config/debug/<event id>`. Viewers SHALL NOT see it.

#### Scenario: Owner follows the link
- **WHEN** the owner taps "Debug" on the card of event `xyz`
- **THEN** the hash becomes `#config/debug/xyz` and `GET /api/debug/motions/xyz` is requested

#### Scenario: Viewer has no link
- **WHEN** a viewer opens Activity
- **THEN** no "Debug" link is shown

### Requirement: Proof stills on Activity
When any change of an event has `proof` links, the event card SHALL show a "Proof" strip with each such change's thumbnails (up to 2), each captioned with the change's label ("+ soda", "− 2 eggs"). The strip SHALL sit beside the clip or stills on screens `sm` and up, and below them on phones. Tapping a thumbnail SHALL open the still viewer on that change's proof stills. Without proof links, no strip SHALL be shown.

#### Scenario: Proof beside the clip
- **WHEN** an event has a `clip` link and a change "+ soda" with 2 `proof` links
- **THEN** the card shows the video and a "Proof" strip with 2 images whose accessible names are "Proof for + soda, 1 of 2" and "Proof for + soda, 2 of 2"

#### Scenario: Several changes
- **WHEN** an event has "+ soda" with 1 proof link and "− 2 eggs" with 2
- **THEN** the strip shows 3 thumbnails, captioned "+ soda" and "− 2 eggs"

#### Scenario: Tap a proof still
- **WHEN** the user taps "Proof for − 2 eggs, 2 of 2"
- **THEN** the still viewer opens on that image, "Next still" is disabled and "Previous still" shows "Proof for − 2 eggs, 1 of 2"

#### Scenario: No proof
- **WHEN** no change of an event has `proof` links
- **THEN** no "Proof" strip is shown, and the clip or stills show as before

#### Scenario: Proof with stills
- **WHEN** an event has `clip: null`, 4 still links and a change with 1 proof link
- **THEN** the 4 still buttons and a "Proof" strip with 1 image are both shown

#### Scenario: Layout by width
- **WHEN** the card is rendered
- **THEN** the media area uses a one-column grid that becomes two columns at `sm` (`sm:grid-cols-[2fr_1fr]`), with the strip in the second column

### Requirement: Clip picker plays face-blurred clips
The Reference images clip picker SHALL offer only the clips that `GET /api/events` returns as `clip` links, and SHALL play no other video. While face blurring is on, those links are face-blurred clips (see `clip-face-blur`). A frame grabbed from a clip SHALL still be sent to `POST /api/camera/frame`, and only the image that route returns SHALL be used.

#### Scenario: Only listed clips offered
- **WHEN** `GET /api/events` returns three recent events, two with a `clip` link and one with `clip: null`
- **THEN** the picker offers exactly the two clips, and its video sources are those two links

#### Scenario: Clip being blurred not offered
- **WHEN** the only recent event has `clip: null` because its clip is still being blurred
- **THEN** the picker shows "No door openings with a clip in the last 7 days."

#### Scenario: Frame still blurred by the server
- **WHEN** the owner picks a frame from a clip
- **THEN** `POST /api/camera/frame` is requested once with that frame, and the reference form shows the image it returns

### Requirement: Privacy mask changed banner
When the warnings include `privacy_mask_changed`, the Fridge screen and every Config tab SHALL show its `message` as a banner with the link "Update door zones" to `#config/doors`. Viewers SHALL see the banner without the link.

#### Scenario: Owner sees the banner and link
- **WHEN** the owner opens the Fridge screen and the warnings include `privacy_mask_changed` with `zones = ["Chiller"]`
- **THEN** a banner shows "The camera's privacy mask changed and now covers part of Chiller…" with an "Update door zones" link that opens `#config/doors`

#### Scenario: Viewer sees no link
- **WHEN** a viewer opens the Fridge screen and the warnings include `privacy_mask_changed`
- **THEN** the banner text is shown with no link

#### Scenario: No camera-moved banner for a mask change
- **WHEN** the warnings include `privacy_mask_changed` and not `camera_moved`
- **THEN** no banner says "The camera has moved or changed angle"

### Requirement: Edit reference images
Each reference card SHALL have an "Edit" button for the owner, next to "Delete". It SHALL open an "Edit reference" sheet showing the reference's current image, ready to draw on and crop, and its annotation in the annotation field. The sheet SHALL offer the same "Choose photo", "Camera snapshot" and "Recent clip" sources as adding, to replace the image. "Save" SHALL be disabled while the annotation is empty or nothing has changed. It SHALL send `PATCH /api/config/references/{id}` with the trimmed annotation if it changed, and the image, resized and with boxes drawn in, only if a new image was chosen, it was cropped or a box was drawn. The list SHALL then show the returned config. A 400 SHALL show the error in the sheet. Viewers get no "Edit" button.

#### Scenario: Edit an annotation
- **WHEN** the owner taps "Edit" on "chocomilk", changes the annotation to `chocolate milk carton` and taps "Save"
- **THEN** the sheet shows the current image, `PATCH` is sent with only `{"annotation": "chocolate milk carton"}`, and the card reads "chocolate milk carton"

#### Scenario: Replace the image
- **WHEN** the owner taps "Edit", chooses a new photo and taps "Save"
- **THEN** `PATCH` is sent with only the resized new image

#### Scenario: Draw on the current image
- **WHEN** the owner taps "Edit", draws a box on the current image and taps "Save"
- **THEN** `PATCH` is sent with only the image, resized with that box

#### Scenario: Nothing changed
- **WHEN** the owner opens "Edit" and changes nothing
- **THEN** "Save" is disabled

#### Scenario: Edit refused
- **WHEN** the API answers 400 to an edit
- **THEN** the error message is shown in the sheet and the list is unchanged

#### Scenario: Viewer has no edit
- **WHEN** a viewer opens the "Reference images" tab
- **THEN** no "Edit" button is shown
