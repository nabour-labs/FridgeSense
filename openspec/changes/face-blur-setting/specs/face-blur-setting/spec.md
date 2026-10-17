# Spec Delta

## Purpose

Lets the owner turn face blurring on or off for the account. It is on by default. While it is on, faces are blurred before any still is stored, analyzed or returned. While it is off, no face detection runs.

## ADDED Requirements

### Requirement: Read the face-blur setting
`GET /api/settings/face-blur` SHALL answer 200 `{"enabled": <bool>}` for the linked account to any signed-in role. When the account has never saved the setting, `enabled` SHALL be `true`.

#### Scenario: Default is on
- **WHEN** the account has never saved the setting and a viewer token calls `GET /api/settings/face-blur`
- **THEN** the response is 200 `{"enabled": true}`

#### Scenario: Saved off
- **WHEN** the owner saved `enabled = false` and a user token calls `GET /api/settings/face-blur`
- **THEN** the response is 200 `{"enabled": false}`

#### Scenario: Not signed in
- **WHEN** `GET /api/settings/face-blur` is called without a token
- **THEN** the response is 401 `{"error": "sign in"}`

### Requirement: Change the face-blur setting
`PUT /api/settings/face-blur` with `{"enabled": true|false}` SHALL save the setting under the linked Ring `account_id`, log `face_blur_changed` with `enabled`, and answer 200 `{"enabled": <saved value>}`. Only the owner SHALL change it: a viewer token gets 403 `{"error": "read-only"}` and a user token gets 403 `{"error": "admin only"}`, and neither changes the setting. A body that is not JSON, or whose `enabled` is not a JSON boolean, SHALL get 400 `{"error": "bad setting"}`. An account with no Ring link SHALL get 409, as other config writes do.

#### Scenario: Owner turns blurring off
- **WHEN** the owner calls `PUT /api/settings/face-blur` with `{"enabled": false}`
- **THEN** the response is 200 `{"enabled": false}`, a later `GET` returns `{"enabled": false}`, and a `face_blur_changed` log line has `enabled = false`

#### Scenario: Owner turns blurring back on
- **WHEN** the setting is off and the owner sends `{"enabled": true}`
- **THEN** the response is 200 `{"enabled": true}` and a later `GET` returns `{"enabled": true}`

#### Scenario: User cannot change it
- **WHEN** a user token sends `{"enabled": false}`
- **THEN** the response is 403 `{"error": "admin only"}` and the setting is unchanged

#### Scenario: Viewer cannot change it
- **WHEN** a viewer token sends `{"enabled": false}`
- **THEN** the response is 403 `{"error": "read-only"}` and the setting is unchanged

#### Scenario: Bad body
- **WHEN** the owner sends `{"enabled": "no"}`, `{"enabled": 0}`, `{}` or a body that is not JSON
- **THEN** the response is 400 `{"error": "bad setting"}` and the setting is unchanged

#### Scenario: Kept per account
- **WHEN** account A's owner turns blurring off
- **THEN** account B's setting still reads `{"enabled": true}`

### Requirement: Unreadable setting counts as on
Every place that blurs faces SHALL read the setting when it handles a still, a snapshot or a frame. For a door event, it SHALL read it once per motion. If the setting cannot be read (any DynamoDB error), it SHALL be treated as on, and a `face_blur_setting_failed` warning SHALL be logged.

#### Scenario: Read fails in the pipeline
- **WHEN** reading the setting raises a DynamoDB `ProvisionedThroughputExceededException` while a door opening's stills are stored
- **THEN** face detection runs on every still as when the setting is on, and a `face_blur_setting_failed` warning is logged

#### Scenario: Read fails for a snapshot
- **WHEN** reading the setting fails during `POST /api/camera/snapshot`
- **THEN** the snapshot is blurred, or the route answers 502 if detection also fails

### Requirement: Blur faces switch on the Camera tab
The Config "Camera" tab SHALL show a "Blur faces" section with a switch reflecting `GET /api/settings/face-blur`, and the text "Blurs faces in stored stills, snapshots and debug traces. Livestream is never blurred." For the owner, the switch SHALL be enabled. Toggling it SHALL send `PUT /api/settings/face-blur` and, on success, show the saved value. On failure it SHALL go back to the previous value and the error SHALL go to the app's normal error handling. For the user and the viewer, the switch SHALL be shown disabled with the current value. While the setting is off, the section SHALL also say "Faces are stored as recorded for 7 days."

#### Scenario: Owner sees it on by default
- **WHEN** the owner opens the Camera tab and the API answers `{"enabled": true}`
- **THEN** an enabled "Blur faces" switch is shown checked

#### Scenario: Owner turns it off
- **WHEN** the owner unchecks "Blur faces" and the API answers 200 `{"enabled": false}`
- **THEN** `PUT /api/settings/face-blur` was sent with `{"enabled": false}`, the switch is unchecked, and "Faces are stored as recorded for 7 days." is shown

#### Scenario: Save fails
- **WHEN** the owner unchecks "Blur faces" and the API answers 500
- **THEN** the switch is checked again

#### Scenario: Others see it read-only
- **WHEN** a user or a viewer opens the Camera tab and the API answers `{"enabled": false}`
- **THEN** the "Blur faces" switch is shown unchecked and disabled, and no `PUT` can be sent
