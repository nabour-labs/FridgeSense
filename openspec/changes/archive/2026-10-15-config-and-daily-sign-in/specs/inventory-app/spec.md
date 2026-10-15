# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
