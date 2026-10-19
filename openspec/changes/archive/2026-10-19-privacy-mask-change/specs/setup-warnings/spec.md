# Spec Delta

## ADDED Requirements

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
