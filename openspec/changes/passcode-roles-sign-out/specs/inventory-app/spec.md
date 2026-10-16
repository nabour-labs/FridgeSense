## ADDED Requirements

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
