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

#### Scenario: Switch to open/close detection
- **WHEN** the user taps the "Open/close detection" tab
- **THEN** the hash becomes `#config/doors`, `GET /api/door-calibration` is requested, and the door references are shown

#### Scenario: Switch to fridge area
- **WHEN** the user taps the "Fridge area" tab
- **THEN** the hash becomes `#config/fridge` and `GET /api/fridge-area` is requested

#### Scenario: Switch to debug
- **WHEN** the owner taps the "Debug" tab
- **THEN** the hash becomes `#config/debug` and `GET /api/debug/motions` is requested

#### Scenario: Open the detection tab by link
- **WHEN** the app is opened at `#config/doors`
- **THEN** the Config screen shows with the "Open/close detection" tab selected

#### Scenario: Open the fridge area tab by link
- **WHEN** the app is opened at `#config/fridge`
- **THEN** the Config screen shows with the "Fridge area" tab selected

#### Scenario: Owner's tabs
- **WHEN** the owner opens Config
- **THEN** the tabs are "Camera", "Reference images", "Open/close detection", "Fridge area" and "Debug", in one row

#### Scenario: Non-owner opens the debug link
- **WHEN** a viewer or user opens `#config/debug`
- **THEN** the "Reference images" tab is shown, as before, and no `/api/debug` request is made

#### Scenario: Viewer sees read-only config
- **WHEN** a viewer opens the "Reference images" tab and the config has one reference and instructions
- **THEN** the reference thumbnail, its annotation and the instructions are shown, with no "Add", "Delete" or "Save" controls

## ADDED Requirements

### Requirement: Debug motion list
The "Debug" tab SHALL list traced motions for one day (today by default, with the same day picker and "Older"/"Newer" paging as Activity). Each row shows the local time, the outcome ("Door opening", "Not the door", "No stills", "Duplicate"), the best score against its threshold, and for door openings the Nova call count, total input and output tokens, cost in USD and total latency. Tapping a row SHALL open `#config/debug/<id>`.

#### Scenario: Not-door row
- **WHEN** a motion at 18:02 has `outcome = "not_door"` and `best = {value: 0.0123, threshold: 0.02}`
- **THEN** its row shows "18:02", "Not the door" and "0.0123 / 0.02", and no Nova figures

#### Scenario: Door opening row
- **WHEN** a door opening has `nova = {calls: 2, input_tokens: 2380, output_tokens: 186, usd: 0.00162, latency_ms: 4040}`
- **THEN** its row shows "2 calls", "2,380 in", "186 out", "$0.0016" and "4.0 s"

#### Scenario: No motions
- **WHEN** no motions were traced on the chosen day
- **THEN** the tab says no motions were recorded on this day

#### Scenario: Open a motion
- **WHEN** the owner taps a row with id `abc`
- **THEN** the hash becomes `#config/debug/abc` and `GET /api/debug/motions/abc` is requested

### Requirement: Debug motion detail
The detail view at `#config/debug/<id>` SHALL show the door section, then one section per Nova call, with a "Back" control to the list. The door section shows every raw still with its time, open/closed verdict and each zone's value against its threshold, with the zone boxes drawn on it. It also shows the rule source, each zone's feature, direction, threshold, margin and baseline, and the door reference images with their status.

#### Scenario: Door section
- **WHEN** a trace has 6 stills, stills 3–4 open, setup rule with 1 `change` zone (threshold 0.11, margin 0.07) and 3 references
- **THEN** 6 still images are shown in order, stills 3 and 4 are marked "Open" and the rest "Closed", each shows its zone 1 value against 0.11, the zone row shows "change", "above", "0.11" and margin "0.07" with its baseline image, and 3 reference images are shown with "open" or "closed"

#### Scenario: Picked stills marked
- **WHEN** stills 3 and 4 were picked for analysis
- **THEN** those two raw stills are marked "Sent to analysis"

#### Scenario: Missing still
- **WHEN** still 5 has `url = null` and `missing_status = 416`
- **THEN** a placeholder reading "Not downloaded (416)" is shown in its place

#### Scenario: Default rule
- **WHEN** the trace's `rule.source = "default"`
- **THEN** the rule is labelled "Default zones" and no baseline or reference images are shown

#### Scenario: Missing detail
- **WHEN** `GET /api/debug/motions/<id>` answers 404
- **THEN** the view says the trace has expired or was never recorded, and "Back" returns to the list

### Requirement: Nova call detail
Each Nova call section SHALL show, in request order, every text block as text and every image (references and stills) as a thumbnail labelled with its role and number, which opens full size when tapped. It then shows the response as formatted JSON with the stop reason, and input, output, cache-read and cache-write tokens, cost, Bedrock latency and wall time.

#### Scenario: Request in order
- **WHEN** a call sent 2 references and 4 stills
- **THEN** the section shows the reference header, "Reference 1: …", reference thumbnail 1, "Reference 2: …", reference thumbnail 2, "Image 1 of 4", still thumbnail 1 … still thumbnail 4, then the instruction text

#### Scenario: Numbers shown
- **WHEN** a call has 1180 input, 96 output, 2000 cache-read and 0 cache-write tokens, `usd = 0.000818`, `latency_ms = 2140` and `wall_ms = 2310`
- **THEN** the section shows "1,180", "96", "2,000", "0", "$0.000818", "2.14 s" and "2.31 s"

#### Scenario: Failed call
- **WHEN** a call has `outcome = "error"` and `error_code = "ThrottlingException"`
- **THEN** the section shows "ThrottlingException" in place of the response and no token figures

#### Scenario: Invalid answer
- **WHEN** a call has `outcome = "invalid"` and `response.stopReason = "end_turn"`
- **THEN** the section is marked "Invalid answer" and shows the response JSON with stop reason "end_turn"

### Requirement: Debug link on Activity
On the Activity screen, each door opening card SHALL show a "Debug" link for the owner that opens `#config/debug/<event id>`. Viewers SHALL NOT see it.

#### Scenario: Owner follows the link
- **WHEN** the owner taps "Debug" on the card of event `xyz`
- **THEN** the hash becomes `#config/debug/xyz` and `GET /api/debug/motions/xyz` is requested

#### Scenario: Viewer has no link
- **WHEN** a viewer opens Activity
- **THEN** no "Debug" link is shown
