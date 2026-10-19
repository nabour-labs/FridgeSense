# Spec Delta

## ADDED Requirements

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
