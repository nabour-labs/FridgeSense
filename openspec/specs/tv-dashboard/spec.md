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
The "In the fridge" panel SHALL list in-stock items (quantity above 0) grouped by category in the Fridge screen's category order, each with its item icon, name and quantity (as on the Fridge screen: the item name and "×<quantity>"), and SHALL leave out items with quantity 0. It SHALL show at most 12 items; when more are in stock it SHALL show the first 12 in that order and then "+N more". With no in-stock items it SHALL show "The fridge is empty". It SHALL refresh from `GET /api/inventory` every 10 s while the page is visible.

#### Scenario: Items by category
- **WHEN** the inventory has eggs (6, dairy), milk (1, dairy), apple (3, produce) and soda can (0, beverage)
- **THEN** the panel shows a "Dairy" group with eggs ×6 and milk ×1, a "Produce" group with apple ×3, and no soda can

#### Scenario: More than fits
- **WHEN** 15 items are in stock
- **THEN** the panel shows 12 items and "+3 more"

#### Scenario: Empty fridge
- **WHEN** no item has a quantity above 0
- **THEN** the panel shows "The fridge is empty"

#### Scenario: Inventory refresh
- **WHEN** 10 s pass while the page is visible
- **THEN** `GET /api/inventory` is requested again and the panel shows the new items

### Requirement: Recent changes panel
The "Recent changes" panel SHALL show the 5 newest door openings from `GET /api/events?days=7`, newest first, each with how long ago it opened (as on the Activity screen) and its changes as labels in the Activity screen's format (`changeLabel`: "+ 2 milk", "− eggs"). Rejected changes SHALL be left out. An opening still being analyzed SHALL show "Checking…"; one with no changes SHALL show "No changes". With no openings it SHALL show "No door openings this week". It SHALL refresh every 30 s while the page is visible.

#### Scenario: Newest five
- **WHEN** the API returns 7 openings
- **THEN** the panel lists the 5 newest, newest first

#### Scenario: Change labels
- **WHEN** an opening 2 minutes ago added 2 milk and removed 1 egg, and a rejected change added 1 apple
- **THEN** its row shows "2 min ago", "+ 2 milk" and "− eggs", and no "apple"

#### Scenario: Analysis running
- **WHEN** an opening has `status = "analyzing"`
- **THEN** its row shows "Checking…"

#### Scenario: Quiet week
- **WHEN** the API returns no openings
- **THEN** the panel shows "No door openings this week"

### Requirement: Opens panel
The "Opens" panel SHALL show the number of door openings today and a bar chart of opens per day for the last 7 days (today last), in the device's time zone, using the same counting as the Stats screen. It SHALL use the openings already loaded for the Recent changes panel.

#### Scenario: Today's count
- **WHEN** the openings include 3 today and 2 yesterday in the device's time zone
- **THEN** the panel shows "3 opens today" and the chart's last bar is 3 and the one before it 2

#### Scenario: One opening today
- **WHEN** exactly one opening happened today
- **THEN** the panel shows "1 open today"

### Requirement: Panels fail on their own
A panel whose data has never loaded and whose last request failed SHALL show "No Data" in place of its content; the other panels SHALL keep showing their data. A failed refresh SHALL keep the data already shown. Errors SHALL be reported as elsewhere in the app (a 401 returns to the passcode screen).

#### Scenario: Events fail, inventory loads
- **WHEN** `GET /api/events` fails and `GET /api/inventory` succeeds
- **THEN** the Recent changes and Opens panels show "No Data" and the In the fridge panel shows the items

#### Scenario: Session expired on the TV
- **WHEN** `GET /api/inventory` answers 401 while the TV dashboard is shown
- **THEN** the passcode screen is shown

### Requirement: Nothing private or interactive on the TV
The TV dashboard SHALL show no stills, clips, live view, reference images or other camera pictures, and SHALL have no buttons, links or inputs. It SHALL request only `GET /api/inventory` and `GET /api/events`, and SHALL NOT handle the Back (Escape) key, so the Fire TV app can close on Back.

#### Scenario: Stills not shown
- **WHEN** an opening in the list has `stills` and change `proof` links
- **THEN** the TV dashboard contains no `img` or `video` element pointing at them

#### Scenario: No controls
- **WHEN** the TV dashboard is shown with items and openings
- **THEN** it contains no button, link or input

#### Scenario: Only two endpoints
- **WHEN** the TV dashboard has loaded and refreshed once
- **THEN** the only API calls made are `inventory` and `events`

#### Scenario: Back is left to the TV app
- **WHEN** the Escape key is pressed on the TV dashboard
- **THEN** the event is not default-prevented and the hash stays `#tv`

### Requirement: Sign in with a remote
At `#tv` with no valid session, the passcode screen SHALL be shown with the passcode field focused, Enter SHALL submit it, and after a successful sign-in the TV dashboard SHALL be shown (the hash stays `#tv`). This SHALL work with the owner, user and viewer passcodes.

#### Scenario: Field focused
- **WHEN** the app opens at `#tv` with no stored session
- **THEN** the passcode field has focus and no inventory request is made

#### Scenario: Enter signs in to the dashboard
- **WHEN** the viewer passcode is typed and Enter is pressed
- **THEN** the session is stored, the hash is still `#tv` and the TV dashboard is shown
