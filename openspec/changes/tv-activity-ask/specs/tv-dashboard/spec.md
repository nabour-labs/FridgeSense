# Spec Delta

## ADDED Requirements

### Requirement: App icon by the title
The header SHALL show the PWA's app icon (`/icon.svg`) immediately left of the "FridgeSense" title, at the title's height, as a decorative image (empty `alt`).

#### Scenario: Icon shown
- **WHEN** the TV dashboard is shown
- **THEN** the header contains an `img` with `src` "/icon.svg" and `alt` "", placed before the "FridgeSense" heading

#### Scenario: Icon shown while data fails
- **WHEN** `GET /api/inventory`, `GET /api/events` and `GET /api/camera` all fail
- **THEN** the header still shows the icon and the "FridgeSense" title

### Requirement: Two pages paged with the remote
The TV dashboard SHALL have two pages: "Overview" (the In the fridge, Recent changes and Opens panels) and "Activity". It SHALL open on Overview. The ArrowRight key SHALL show Activity and ArrowLeft SHALL show Overview; each such key press SHALL be default-prevented. ArrowRight on Activity and ArrowLeft on Overview SHALL do nothing. The header SHALL keep showing on both pages. A page indicator SHALL name both pages ("Overview", "Activity") and mark the one on screen with `aria-current="page"`. Data SHALL keep refreshing on both pages, and switching pages SHALL make no extra requests.

#### Scenario: Opens on the overview
- **WHEN** the TV dashboard is shown
- **THEN** the "In the fridge", "Recent changes" and "Opens" panels are shown, the "Activity" panel is not, and "Overview" has `aria-current="page"`

#### Scenario: Right shows Activity
- **WHEN** ArrowRight is pressed on the overview
- **THEN** the "Activity" panel is shown, the three overview panels are not, "Activity" has `aria-current="page"`, and the key event is default-prevented

#### Scenario: Left goes back
- **WHEN** ArrowLeft is pressed on the Activity page
- **THEN** the overview panels are shown again and "Overview" has `aria-current="page"`

#### Scenario: Keys at the ends do nothing
- **WHEN** ArrowLeft is pressed on the overview, or ArrowRight on the Activity page
- **THEN** the page on screen does not change

#### Scenario: No extra requests when paging
- **WHEN** the dashboard has loaded and ArrowRight then ArrowLeft are pressed
- **THEN** no further `inventory`, `events` or `camera` request is made beyond the regular refreshes

### Requirement: Activity page
The Activity page SHALL show the loaded door openings from the last 7 days, newest first, as many as fit, one row each. A row SHALL show "<Today|Yesterday|weekday> · <local clock time> · <duration in seconds> s" (duration left out when unknown); then the change labels joined by ", " (as on Recent changes), "Checking…" while the opening is still being analyzed, or "No changes"; then up to 4 of the opening's `stills` (the first 4 links, `alt` ""), and the opening's proof photos (one per change that has a `proof` link, its first link, rejected changes skipped, at most 3, `alt` ""). An opening with no stills and no proof SHALL show no pictures. With no openings in the last 7 days it SHALL read "No door openings this week". If `GET /api/events` fails before any openings have loaded it SHALL read "No Data".

#### Scenario: Opening with changes, stills and proof
- **WHEN** today at 10:36 am an opening of 18 s added a bowl with `proof` ["https://s3/p.jpg"] and has `stills` ["https://s3/1.jpg", "https://s3/2.jpg"]
- **THEN** its row reads "Today · 10:36 am · 18 s" and "+ bowl", and shows `img` elements with `src` "https://s3/1.jpg", "https://s3/2.jpg" and "https://s3/p.jpg"

#### Scenario: At most four stills
- **WHEN** an opening has 6 `stills`
- **THEN** its row shows only the first 4

#### Scenario: Every opening has its own row
- **WHEN** three openings in a row have no changes
- **THEN** the Activity page shows three rows reading "No changes", not one "3 openings" row

#### Scenario: Still being analyzed
- **WHEN** an opening's analysis has not finished
- **THEN** its row reads "Checking…" and shows its stills but no proof photos

#### Scenario: Older than a week left out
- **WHEN** the loaded openings include one from 9 days ago
- **THEN** the Activity page has no row for it

#### Scenario: Nothing this week
- **WHEN** no loaded opening is from the last 7 days
- **THEN** the Activity page reads "No door openings this week"

#### Scenario: Events fail
- **WHEN** `GET /api/events` fails before any openings have loaded and the Activity page is shown
- **THEN** the Activity panel reads "No Data"

### Requirement: Ask by voice
When the browser has speech recognition (`SpeechRecognition` or `webkitSpeechRecognition`), the header SHALL show a button named "Ask a question" with a microphone icon, and it SHALL have focus when the dashboard first shows, so the remote's select button presses it. Without speech recognition the button SHALL NOT be shown. Pressing the button SHALL start listening in "en-US" with final results only, and SHALL show "Listening…". The first final result SHALL be sent as `POST /api/ask` with body `{"question": "<what was heard, trimmed>"}`. While waiting, the dashboard SHALL show the question and "Thinking…". When the answer arrives it SHALL show the question and the `answer` text in a banner under the header, on either page, and SHALL play `audio` as `data:audio/mpeg;base64,<audio>`; when `audio` is null or won't play, it SHALL read `answer` with speech synthesis. The banner SHALL disappear 20 seconds after the answer is shown, or when another question starts. Pressing the button again while listening SHALL stop listening and send nothing. If nothing was heard, the banner SHALL read "Didn't catch that. Try again." If `POST /api/ask` fails, it SHALL read "Couldn't get an answer. Try again."

#### Scenario: No speech recognition
- **WHEN** neither `SpeechRecognition` nor `webkitSpeechRecognition` exists
- **THEN** the dashboard contains no "Ask a question" button

#### Scenario: Mic has focus
- **WHEN** the dashboard is shown and speech recognition exists
- **THEN** the "Ask a question" button is the focused element

#### Scenario: Spoken question answered
- **WHEN** the button is pressed, the recognizer returns the final result "do I have milk", and `POST /api/ask` answers `{"answer": "Yes, you have 2 milk.", "audio": "SUQz"}`
- **THEN** the request body is `{"question": "do I have milk"}`, the banner shows "do I have milk" and "Yes, you have 2 milk.", and audio plays from `data:audio/mpeg;base64,SUQz`

#### Scenario: No audio in the answer
- **WHEN** `POST /api/ask` answers with `"audio": null`
- **THEN** the answer is read with speech synthesis

#### Scenario: Listening shown
- **WHEN** the button is pressed
- **THEN** "Listening…" is shown and the recognizer was started with `lang` "en-US" and `interimResults` false

#### Scenario: Stopped while listening
- **WHEN** the button is pressed, then pressed again before any result
- **THEN** listening stops and no `POST /api/ask` request is made

#### Scenario: Nothing heard
- **WHEN** listening ends with no final result
- **THEN** the banner reads "Didn't catch that. Try again." and no `POST /api/ask` request is made

#### Scenario: Ask fails
- **WHEN** `POST /api/ask` fails
- **THEN** the banner reads "Couldn't get an answer. Try again."

#### Scenario: Banner goes away
- **WHEN** an answer has been shown for 20 seconds
- **THEN** the banner is gone

#### Scenario: Answer on the Activity page
- **WHEN** an answer arrives while the Activity page is shown
- **THEN** the banner is shown and the Activity page stays on screen

## MODIFIED Requirements

### Requirement: Nothing private or interactive on the TV dashboard
The TV dashboard SHALL show no clips, video, live view, reference images, camera snapshots or the camera's product image; the only pictures it SHALL show are the app icon and the door-opening stills and proof photos from `GET /api/events`. Its only control SHALL be the "Ask a question" button; it SHALL have no links or inputs. It SHALL request only `GET /api/inventory`, `GET /api/events` and `GET /api/camera`, plus `POST /api/ask` after a question has been heard, and SHALL NOT handle the Back (Escape) key, so the Fire TV app can close on Back.

#### Scenario: No clips or video
- **WHEN** an opening in the list has a `clip` link, on either page
- **THEN** the TV dashboard contains no `video` element and nothing pointing at the clip

#### Scenario: Only opening pictures and the icon shown
- **WHEN** the TV dashboard is shown with openings that have `stills` and change `proof` links, on either page
- **THEN** every `img` `src` on the dashboard is "/icon.svg" or one of those links

#### Scenario: Camera image not shown
- **WHEN** `GET /api/camera` returns an `image_url`
- **THEN** the TV dashboard contains no `img` element pointing at it

#### Scenario: Only the mic button
- **WHEN** the TV dashboard is shown with items, openings with photos, camera details and speech recognition available, on either page
- **THEN** its only button is "Ask a question", and it contains no link or input

#### Scenario: Only the listed endpoints
- **WHEN** the TV dashboard has loaded and refreshed once, and no question was asked
- **THEN** the only API calls made are `inventory`, `events` and `camera`, and `POST /api/camera/snapshot` and `POST /api/ask` are never requested

#### Scenario: Back is left to the TV app
- **WHEN** the Escape key is pressed on either page
- **THEN** the event is not default-prevented, the hash stays `#tv` and the page on screen does not change

### Requirement: Photos load quietly
A photo on the TV dashboard (a proof photo or an Activity still) that fails to load SHALL be removed instead of showing a broken image, without affecting the rest of its row. When an events refresh returns a new link for the same picture (same address without its query string) that is already shown, the TV dashboard SHALL keep showing it with its current link, so it is not downloaded again.

#### Scenario: Broken link hidden
- **WHEN** a proof photo's `img` fires an `error` event
- **THEN** that `img` is removed, and the row's labels and its other photos stay

#### Scenario: Broken Activity still hidden
- **WHEN** an Activity still's `img` fires an `error` event
- **THEN** that `img` is removed, and the row's time, labels and other pictures stay

#### Scenario: Re-signed link kept
- **WHEN** a proof photo is shown with `src` "https://s3/a.jpg?X-Amz-Signature=1" and the next events refresh returns "https://s3/a.jpg?X-Amz-Signature=2" for it
- **THEN** its `img` `src` is still "https://s3/a.jpg?X-Amz-Signature=1"

## REMOVED Requirements

### Requirement: Latest still in the header
**Reason**: Jayson asked for it to go (2026-10-20); the proof photos and the new Activity page show the openings' pictures, and the header needs the room for the icon and the mic button.
**Migration**: None. The header shows the icon, title, camera line, mic button and "Updated" time; opening pictures are on Recent changes and the Activity page.
