# Spec Delta

## ADDED Requirements

### Requirement: Banners shown to the owner only
The app SHALL show setup-warning banners only to a session with role `owner`. For `user` and `viewer` sessions the app SHALL show no warning banner on any screen and SHALL NOT call `GET /api/warnings`. The API itself is unchanged.

#### Scenario: Owner sees banners
- **WHEN** an owner opens the Fridge screen and `GET /api/warnings` lists `camera_moved`
- **THEN** the banner shows its message and its fix links

#### Scenario: User sees no banners
- **WHEN** a session with role `user` opens the Fridge or Config screen while a warning is active
- **THEN** no warning banner is shown and `GET /api/warnings` is not called

#### Scenario: Viewer sees no banners
- **WHEN** a session with role `viewer` opens the Fridge or Config screen while a warning is active
- **THEN** no warning banner is shown and `GET /api/warnings` is not called

## MODIFIED Requirements

### Requirement: Monitoring paused warning
When the account's first discovered camera is paused, `GET /api/warnings` SHALL list `{"code": "monitoring_paused", "message": "FridgeSense is paused, so door openings are not recorded.", "since": "<ISO 8601 UTC>"}` before every other warning. The other warnings SHALL still be checked. In the app, the banner's fix link for this warning SHALL read "Resume on Camera tab" and go to `#config`.

#### Scenario: Paused
- **WHEN** the camera was paused at `2026-10-18T14:05:00.000Z`
- **THEN** `warnings[0]` is `{"code": "monitoring_paused", "message": "FridgeSense is paused, so door openings are not recorded.", "since": "2026-10-18T14:05:00.000Z"}`

#### Scenario: Paused with other problems
- **WHEN** the camera is paused and door setup never ran
- **THEN** `warnings` lists `monitoring_paused` then `door_setup_missing`

#### Scenario: Active
- **WHEN** the camera is active
- **THEN** no `monitoring_paused` warning is listed

#### Scenario: Banner link
- **WHEN** an owner opens the Fridge screen and `GET /api/warnings` lists `monitoring_paused`
- **THEN** the banner shows its message and a "Resume on Camera tab" link to `#config`
