# setup-warnings Specification

## Purpose
Lists the setup problems that silently stop door openings being recorded or detected well, through `GET /api/warnings` and the app's warning banner, each with what fixes it.

## Requirements

### Requirement: Ring account needs re-linking warning
When the stored Ring account has `link_status = "needs_relink"`, `GET /api/warnings` SHALL list `{"code": "needs_relink", "message": "The Ring account link has expired, so door openings are not recorded. Re-link the Ring account in the Ring app."}` before every other warning, even when no camera has been discovered. The other warnings SHALL still be checked. In the app, the banner SHALL show the message with no fix link.

#### Scenario: Link expired
- **WHEN** the token store holds `link_status = "needs_relink"` and every other check passes
- **THEN** `warnings` is `[{"code": "needs_relink", "message": "The Ring account link has expired, so door openings are not recorded. Re-link the Ring account in the Ring app."}]`

#### Scenario: Link expired with other problems
- **WHEN** the link needs re-linking and door setup never ran
- **THEN** `warnings` lists `needs_relink` then `door_setup_missing`

#### Scenario: Link expired before any camera
- **WHEN** the link needs re-linking and no camera has been discovered
- **THEN** `warnings` is the `needs_relink` warning alone

#### Scenario: Linked
- **WHEN** the token store holds `link_status = "linked"`
- **THEN** no `needs_relink` warning is listed

#### Scenario: Re-link banner
- **WHEN** an owner opens the Fridge screen and `GET /api/warnings` lists `needs_relink`
- **THEN** the banner shows its message and no link

### Requirement: Privacy mask changed warning
`GET /api/warnings` SHALL include `{"code": "privacy_mask_changed", "message": "The camera's privacy mask changed and now covers part of <zones>. Move those door zones or the mask, then retake their door references.", "since": "<mask_changed_at>", "zones": [...]}` while the device's alignment has a non-empty `mask_zones`. `<zones>` SHALL be the zone names joined as "A", "A and B", or "A, B and C", and `zones` SHALL list the same names. A mask change SHALL never add `camera_moved`. If the alignment can't be read, the warning SHALL be left out and the other warnings still returned.

#### Scenario: One zone covered
- **WHEN** the alignment has `mask_zones = ["Chiller"]` and `mask_changed_at` = 2026-10-18T21:32:14Z
- **THEN** the warnings include `{"code": "privacy_mask_changed", "message": "The camera's privacy mask changed and now covers part of Chiller. Move those door zones or the mask, then retake their door references.", "since": "2026-10-18T21:32:14.000Z", "zones": ["Chiller"]}`

#### Scenario: Three zones covered
- **WHEN** `mask_zones = ["Chiller", "Freezer Drawer 1", "Freezer Drawer 2"]`
- **THEN** the message says "covers part of Chiller, Freezer Drawer 1 and Freezer Drawer 2"

#### Scenario: Mask change with no zone covered
- **WHEN** the mask changed but `mask_zones` is empty and `moved` is false
- **THEN** neither `privacy_mask_changed` nor `camera_moved` is listed

#### Scenario: Cleared by a setup run
- **WHEN** `mask_zones = ["Chiller"]` and the owner runs setup successfully
- **THEN** `privacy_mask_changed` is no longer listed

#### Scenario: Alignment unreadable
- **WHEN** reading the alignment item raises an error
- **THEN** `GET /api/warnings` answers 200 without `privacy_mask_changed` and with the other warnings
