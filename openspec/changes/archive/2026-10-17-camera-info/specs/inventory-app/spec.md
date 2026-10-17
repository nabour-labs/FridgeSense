# Spec Delta

## MODIFIED Requirements

### Requirement: Config screen
The app SHALL offer a Config screen, opened by a "Config" gear button in the header. Its tabs are "Camera" at `#config` (the default), "Reference images" at `#config/refs`, "Open/close detection" at `#config/doors`, "Fridge area" at `#config/fridge` and, for the owner only, "Debug" at `#config/debug`. Switching tabs SHALL update the hash, and opening any of these hashes SHALL show that tab. The tabs SHALL fit side by side at 375 px without horizontal scrolling. Viewers get no edit controls.

#### Scenario: Open config
- **WHEN** the signed-in user taps the gear button
- **THEN** the header title reads "Config", the "Camera" tab is selected, `GET /api/camera` is requested, and the location hash is `#config`

#### Scenario: Reference images tab
- **WHEN** the user selects the "Reference images" tab
- **THEN** the location hash is `#config/refs`, `GET /api/config` is requested, and the "Reference images" and "Custom instructions" sub-sections are shown

#### Scenario: Direct link to reference images
- **WHEN** the app opens at `#config/refs`
- **THEN** the "Reference images" tab is selected

#### Scenario: Owner's tabs
- **WHEN** the owner opens Config
- **THEN** the tabs are "Camera", "Reference images", "Open/close detection", "Fridge area" and "Debug", in one row

#### Scenario: Non-owner opens the debug link
- **WHEN** a viewer or user opens `#config/debug`
- **THEN** the "Reference images" tab is shown, as before, and no `/api/debug` request is made

#### Scenario: Viewer sees read-only config
- **WHEN** a viewer opens the "Reference images" tab and the config has one reference and instructions
- **THEN** the reference thumbnail, its annotation and the instructions are shown, with no "Add", "Delete" or "Save" controls
