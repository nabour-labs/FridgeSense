# Spec Delta

## ADDED Requirements

### Requirement: Setup warning banners
The Fridge screen and every Config tab SHALL request `GET /api/warnings` when shown and show each warning as a banner with its `message`. Each banner links to its fix: `motion_detection_off` to the Camera tab, `door_setup_missing` to "Set up detection" (`#config/doors`), and `camera_moved` to "Update door references" (`#config/doors`) and/or "Update fridge area" (`#config/fridge`), one link per entry in `update`. Viewers see the banners without links. A failed request shows no banner and no error.

#### Scenario: Motion detection off banner
- **WHEN** the Fridge screen loads and the warnings include `motion_detection_off`
- **THEN** a banner shows its message with a link to the Camera tab

#### Scenario: Setup missing banner
- **WHEN** the warnings include `door_setup_missing`
- **THEN** a banner shows "Open/close detection is not set up…" with a "Set up detection" link that opens `#config/doors`

#### Scenario: Camera moved banner with both links
- **WHEN** the warnings include `camera_moved` with `update = ["door_references", "fridge_area"]`
- **THEN** the banner shows the message and the links "Update door references" (`#config/doors`) and "Update fridge area" (`#config/fridge`)

#### Scenario: Camera moved banner with one link
- **WHEN** `camera_moved` has `update = ["fridge_area"]`
- **THEN** only the "Update fridge area" link is shown

#### Scenario: Viewer sees no links
- **WHEN** a viewer opens the Fridge screen and the warnings include `door_setup_missing`
- **THEN** the banner text is shown with no link

#### Scenario: No warnings
- **WHEN** `warnings = []`
- **THEN** no banner is shown

#### Scenario: Warnings request fails
- **WHEN** `GET /api/warnings` answers 500
- **THEN** the Fridge screen shows its items with no banner and no error notice

### Requirement: Alignment and tuning on the Open/close detection tab
The "Open/close detection" tab SHALL show, under the setup result, "Adjusted for camera shift of <dx>% across, <dy>% down (checked <time>)" when `alignment.checked_at` is set, and "Tuned from <tuned_from> recent openings, <time>" when `setup.tuned_at` is set. When `alignment.moved` is true, it SHALL show "Camera moved: add new references and run setup."

#### Scenario: Shift and tuning shown
- **WHEN** the body has `alignment.dx = 0.016`, `alignment.dy = 0`, `checked_at` set, and `setup.tuned_from = 8`
- **THEN** the tab shows "Adjusted for camera shift of 1.6% across, 0% down" and "Tuned from 8 recent openings"

#### Scenario: Moved notice
- **WHEN** `alignment.moved` is true
- **THEN** the tab shows "Camera moved: add new references and run setup."

#### Scenario: Nothing yet
- **WHEN** `alignment.checked_at` is null and `setup.tuned_at` is null
- **THEN** neither line is shown
