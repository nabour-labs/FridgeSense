# tv-dashboard Specification

## Purpose
TBD - created by archiving change firetv-kitchen-dashboard. Update Purpose after archive.

## Requirements

### Requirement: TV route
When the app is opened or navigated to with the hash `#tv` and has a valid session, it SHALL show the TV dashboard in place of the tabbed app: no bottom tabs, no Config link, no Sign out button and no debug bar. Any other hash SHALL show the tabbed app as before.

#### Scenario: Open at #tv
- **WHEN** a signed-in app is opened at `#tv`
- **THEN** the "TV dashboard" region is shown and there is no "Fridge" tab button and no "Config" link

#### Scenario: Other hashes unchanged
- **WHEN** a signed-in app is opened at `#fridge`
- **THEN** the tabbed app with the Fridge screen is shown and no "TV dashboard" region exists

#### Scenario: Switch to #tv while open
- **WHEN** the app shows the Fridge screen and the hash changes to `#tv`
- **THEN** the TV dashboard is shown without reloading the page

### Requirement: In the fridge panel
The "In the fridge" panel SHALL list in-stock items (quantity above 0) grouped by category in the Fridge screen's category order, each with its TV icon, name and quantity (as on the Fridge screen: the item name and "×<quantity>"), and SHALL leave out items with quantity 0 from the list. It SHALL show at most 12 items; when more are in stock it SHALL show the first 12 in that order and then "+N more". With no in-stock items it SHALL show "The fridge is empty". When items have quantity 0, the panel SHALL end with "Out: " and their names in inventory order, separated by ", ", at most 6, then ", +N more"; with none it SHALL show no "Out:" line. It SHALL refresh from `GET /api/inventory` every 10 s while the page is visible.

#### Scenario: Items by category
- **WHEN** the inventory has eggs (6, dairy), milk (1, dairy), apple (3, produce) and soda can (0, beverage)
- **THEN** the panel shows a "Dairy" group with eggs ×6 and milk ×1, a "Produce" group with apple ×3, and soda can is not in any group

#### Scenario: More than fits
- **WHEN** 15 items are in stock
- **THEN** the panel shows 12 items and "+3 more"

#### Scenario: Empty fridge
- **WHEN** no item has a quantity above 0
- **THEN** the panel shows "The fridge is empty"

#### Scenario: Out of stock
- **WHEN** the inventory has milk (0), eggs (0) and cheese (2), in that order
- **THEN** the panel shows "Out: milk, eggs"

#### Scenario: Many out of stock
- **WHEN** 8 items have quantity 0
- **THEN** the "Out:" line names the first 6 in inventory order and ends with ", +2 more"

#### Scenario: Nothing out of stock
- **WHEN** every item has a quantity above 0
- **THEN** the panel has no "Out:" line

#### Scenario: Inventory refresh
- **WHEN** 10 s pass while the page is visible
- **THEN** `GET /api/inventory` is requested again and the panel shows the new items

### Requirement: Recent changes panel
The "Recent changes" panel SHALL show the newest door openings of the last 7 days from the openings loaded for the dashboard, newest first, as at most 5 rows. Each row SHALL show how long ago it opened (as on the Activity screen), the local clock time it opened (e.g. "8:42 pm") and how long the door stayed open in whole seconds (e.g. "12 s"), joined by " · ", then its changes as labels in the Activity screen's format ("+ 2 milk", "− eggs"). Rejected changes SHALL be left out. An opening still being analyzed SHALL show "Checking…"; one with no changes SHALL show "No changes". Two or more back-to-back openings (adjacent in newest-first order) that all have no changes and are not being analyzed SHALL be shown as one row with the newest one's time and duration and "<N> openings · No changes". With no openings in the last 7 days it SHALL show "No door openings this week". It SHALL refresh every 30 s while the page is visible.

#### Scenario: Newest five
- **WHEN** the openings include 7 in the last 7 days, each with changes
- **THEN** the panel lists 5 rows, the 5 newest, newest first

#### Scenario: Time and duration
- **WHEN** an opening 2 minutes ago, at 8:42 pm local time, stayed open for 12.4 s
- **THEN** its row shows "2 min ago · 8:42 pm · 12 s"

#### Scenario: Change labels
- **WHEN** an opening added 2 milk and removed 1 egg, and a rejected change added 1 apple
- **THEN** its row shows "+ 2 milk" and "− eggs", and no "apple"

#### Scenario: Analysis running
- **WHEN** an opening has `status = "analyzing"`
- **THEN** its row shows "Checking…" and it is not collapsed with others

#### Scenario: No-change openings collapse
- **WHEN** the newest openings, newest first, are: no changes (8:50 pm), no changes, no changes, then one that added beer
- **THEN** the first row shows "8:50 pm" and "3 openings · No changes", and the second row shows "+ beer"

#### Scenario: Single no-change opening
- **WHEN** an opening with no changes sits between two openings with changes
- **THEN** its row shows "No changes" with no opening count

#### Scenario: Quiet week
- **WHEN** the only opening loaded is 10 days old, or none is
- **THEN** the panel shows "No door openings this week"

### Requirement: Opens panel
The "Opens" panel SHALL show the number of door openings today, today's open time as "Avg <a> s · Longest <l> s" (using the Stats screen's rounding; left out when there are no openings today), a bar chart of opens per day for the last 7 days (today last), and a heatmap of opens by weekday (rows, Sunday first) and hour (24 columns) over all loaded openings (the last 28 days), shaded with the Stats screen's 0–4 levels. All counts SHALL be in the device's time zone and use the same counting as the Stats screen, from the openings already loaded for the dashboard.

#### Scenario: Today's count
- **WHEN** the openings include 3 today and 2 yesterday in the device's time zone
- **THEN** the panel shows "3 opens today" and the chart's last bar is 3 and the one before it 2

#### Scenario: One opening today
- **WHEN** exactly one opening happened today
- **THEN** the panel shows "1 open today"

#### Scenario: Open time today
- **WHEN** today's openings lasted 10 s, 14 s and 40 s
- **THEN** the panel shows "Avg 21 s · Longest 40 s"

#### Scenario: No openings today
- **WHEN** no opening happened today
- **THEN** the panel shows "0 opens today" and no "Avg" text

#### Scenario: Heatmap
- **WHEN** the openings include 4 on Mondays at 8 am local time and 1 on a Tuesday at 6 pm, all within the last 28 days
- **THEN** the heatmap has 7 rows of 24 cells, the Monday 8 am cell is labelled "Mon 8 am: 4 opens" at level 4, the Tuesday 6 pm cell is labelled "Tue 6 pm: 1 open" at level 1, and every other cell is at level 0

### Requirement: Panels fail on their own
A panel or line whose data has never loaded and whose last request failed SHALL show "No Data" in place of its content; the others SHALL keep showing their data. A failed refresh SHALL keep the data already shown. Errors SHALL be reported as elsewhere in the app (a 401 returns to the passcode screen).

#### Scenario: Events fail, inventory loads
- **WHEN** `GET /api/events` fails and `GET /api/inventory` succeeds
- **THEN** the Recent changes and Opens panels show "No Data" and the In the fridge panel shows the items

#### Scenario: Camera fails, panels load
- **WHEN** `GET /api/camera` fails and the other two requests succeed
- **THEN** the camera line shows "Camera: No Data" and all three panels show their data

#### Scenario: Session expired on the TV
- **WHEN** `GET /api/inventory` answers 401 while the TV dashboard is shown
- **THEN** the passcode screen is shown

### Requirement: Sign in with a remote
At `#tv` with no valid session, the passcode screen SHALL be shown with the passcode field focused, Enter SHALL submit it, and after a successful sign-in the TV dashboard SHALL be shown (the hash stays `#tv`). This SHALL work with the owner, user and viewer passcodes.

#### Scenario: Field focused
- **WHEN** the app opens at `#tv` with no stored session
- **THEN** the passcode field has focus and no inventory request is made

#### Scenario: Enter signs in to the dashboard
- **WHEN** the viewer passcode is typed and Enter is pressed
- **THEN** the session is stored, the hash is still `#tv` and the TV dashboard is shown

### Requirement: Nothing private or interactive on the TV dashboard
The TV dashboard SHALL show no stills, clips, live view, reference images, the camera's product image or other camera pictures, and SHALL have no buttons, links or inputs. It SHALL request only `GET /api/inventory`, `GET /api/events` and `GET /api/camera`, and SHALL NOT handle the Back (Escape) key, so the Fire TV app can close on Back.

#### Scenario: Camera image not shown
- **WHEN** `GET /api/camera` returns an `image_url`
- **THEN** the TV dashboard contains no `img` element pointing at it

#### Scenario: No controls
- **WHEN** the TV dashboard is shown with items, openings and camera details
- **THEN** it contains no button, link or input

#### Scenario: Only three endpoints
- **WHEN** the TV dashboard has loaded and refreshed once
- **THEN** the only API calls made are `inventory`, `events` and `camera`

#### Scenario: Back is left to the TV app
- **WHEN** the Escape key is pressed on the TV dashboard
- **THEN** the event is not default-prevented and the hash stays `#tv`

### Requirement: Openings loaded for the dashboard
The TV dashboard SHALL load door openings with `GET /api/events?days=28` and use them for the Recent changes and Opens panels.

#### Scenario: Four weeks requested
- **WHEN** the TV dashboard loads
- **THEN** the events request asks for `days=28`

### Requirement: Camera status line
Under the title, the TV dashboard SHALL show one line about the camera from `GET /api/camera`, its parts joined by " · ": the camera's name; "Online" when `online` is true, "Offline" when false, and "Status unknown" when null or when `ring` is "unavailable"; "Paused" when `monitoring.paused` is true; "<p>% uptime" from `uptime.percent` (one decimal place; left out when null); and "Motion detection on" or "Motion detection off" from `motion_detection` (left out when null). It SHALL refresh every 5 minutes while the page is visible.

#### Scenario: Camera online
- **WHEN** the camera is "Fridge Cam", online, not paused, with 99.2% uptime and motion detection on
- **THEN** the line reads "Fridge Cam · Online · 99.2% uptime · Motion detection on"

#### Scenario: Camera offline
- **WHEN** `online` is false and `uptime.percent` is 75
- **THEN** the line includes "Offline" and "75.0% uptime"

#### Scenario: Ring unavailable
- **WHEN** the response has `ring: "unavailable"`, `online: null`, `motion_detection: null` and `uptime.percent: null`
- **THEN** the line reads "<name> · Status unknown"

#### Scenario: Monitoring paused
- **WHEN** `monitoring.paused` is true
- **THEN** the line includes "Paused"

#### Scenario: Camera refresh
- **WHEN** 5 minutes pass while the page is visible
- **THEN** `GET /api/camera` is requested again, and it was not requested again before then

### Requirement: Updated time
The TV dashboard's header SHALL show "Updated <time>" with the local clock time (e.g. "8:45 pm") of the latest successful inventory or events load, and nothing before the first one succeeds.

#### Scenario: Updated after load
- **WHEN** inventory loads successfully at 8:45 pm local time
- **THEN** the header shows "Updated 8:45 pm"

#### Scenario: Nothing loaded yet
- **WHEN** neither inventory nor events has loaded
- **THEN** the header shows no "Updated" text

### Requirement: Icons the TV can draw
On the TV dashboard, an item whose icon would be 🫙 SHALL show 🧂 and one whose icon would be 🫑 SHALL show 🌶️; every other item keeps the app's icon. The phone app's icons SHALL NOT change.

#### Scenario: Condiment on the TV
- **WHEN** the inventory has "condiment" (category condiment) and "ketchup" (category condiment) in stock
- **THEN** both rows on the TV show 🧂, and none shows 🫙

#### Scenario: Pepper on the TV
- **WHEN** the inventory has "bell pepper" in stock
- **THEN** its row on the TV shows 🌶️

#### Scenario: Phone unchanged
- **WHEN** the Fridge screen shows "ketchup"
- **THEN** its icon is 🫙

### Requirement: No pointer over the dashboard
The TV dashboard SHALL hide the mouse pointer (CSS `cursor: none` on the whole dashboard), so the remote's cursor does not cover the panels.

#### Scenario: Pointer hidden
- **WHEN** the TV dashboard is shown
- **THEN** its root element has the computed style `cursor: none`
