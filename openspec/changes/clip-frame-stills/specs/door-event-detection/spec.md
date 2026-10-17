# Spec Delta

## MODIFIED Requirements

### Requirement: Stills for an opening found in the clip
For a door opening found in the clip, the system SHALL pick up to 4 frames from the open span. The span runs from the first open frame through the first closed frame after the last open one. The picks are evenly spaced and always include the span's first and last frame. Each picked clip frame, encoded as JPEG, SHALL be used as that still; the system SHALL NOT request Ring stills for them, since Ring's still at a timestamp can show a different moment than the frame the door check scored. These stills are then cropped, face-blurred, stored as `still-<n>.jpg` and analyzed exactly as stills are today.

#### Scenario: Four stills from the open span
- **WHEN** the frame interval is 500 ms, the frames at offsets 4000–12000 ms are open and the frame at 12500 ms is closed
- **THEN** the clip frames at offsets 4000, 7000, 9500 and 12500 ms are face-blurred and stored as `still-1.jpg` … `still-4.jpg`

#### Scenario: Short open span
- **WHEN** only the frame at offset 6000 ms is open and the frame at 6500 ms is closed
- **THEN** exactly two stills are stored, the clip frames at offsets 6000 and 6500 ms

#### Scenario: No Ring still requested
- **WHEN** a door opening is found in the clip and Ring would answer still requests with a closed-door image
- **THEN** no request is made to `POST /v1/devices/{device_id}/media/image/download`, and each stored still is the JPEG clip frame (the lit frame at offset 7000 ms for `still-2.jpg`), not Ring's image

#### Scenario: Still missing, frame used
- **WHEN** Ring would answer 403 for a still at `start_ms` + 7000 ms
- **THEN** the clip frame at offset 7000 ms is face-blurred and stored as that still, and analysis still gets 4 stills
