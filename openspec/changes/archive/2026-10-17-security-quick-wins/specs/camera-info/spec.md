# Spec Delta

## MODIFIED Requirements

### Requirement: Browser decoder readout
For the owner and users, the Camera tab SHALL have a "Decoder" card with a "Check decoder" button that opens the Livestream dialog; viewers SHALL NOT see the card, because they can't open a live view. While video plays, the app SHALL read the browser's WebRTC inbound video stats about once a second and, after the dialog closes, show the last values: codec (e.g. "video/H264"), decoder implementation, frame size (e.g. "1920 × 1080") and frames per second. Before a check it SHALL show "Run a check to see how this browser decodes the camera's video."

#### Scenario: Decoder values after a check
- **WHEN** the user taps "Check decoder", the stats report codec `video/H264`, decoder implementation `ExternalDecoder`, 1920 × 1080 at 15 fps, and the user closes the dialog
- **THEN** the Decoder card shows "video/H264", "ExternalDecoder", "1920 × 1080" and "15 fps"

#### Scenario: Before any check
- **WHEN** the Camera tab opens
- **THEN** the Decoder card shows "Run a check to see how this browser decodes the camera's video." and a "Check decoder" button

#### Scenario: No video played
- **WHEN** the live view fails before any video arrives and the user closes the dialog
- **THEN** the Decoder card still shows the "Run a check…" text

#### Scenario: No Decoder card for a viewer
- **WHEN** the Camera tab is shown to a viewer
- **THEN** no "Decoder" card and no "Check decoder" button are shown
