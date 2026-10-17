# Spec Delta

## ADDED Requirements

### Requirement: Open-span clip stored
For a door opening found in the event clip, the system SHALL cut the clip to the open span (`opened_at` → `closed_at`) without re-encoding and store it as `clip.mp4` under the same prefix as the event's stills. The cut SHALL start at the last keyframe at or before `opened_at`. The system SHALL record on the door event `clip_key` and `clip_span = [start_s, end_s]`: where the open span starts and ends in the stored file, in seconds rounded to 0.1. A failed cut or upload SHALL be logged as `clip_not_stored` with a reason and SHALL NOT fail the step or change its outcome.

#### Scenario: Clip cut to the open span
- **WHEN** the event clip has keyframes every 2.0 s, the open span runs from offset 4500 ms to 12500 ms, and the door check outcome is `door_open`
- **THEN** `clip.mp4` is stored under the stills prefix, starts at the 4.0 s keyframe, ends at or after 12.5 s and lasts under 9.0 s, and the door event has `clip_key` set to its key and `clip_span = [0.5, 8.5]`

#### Scenario: Door still open at the end of the clip
- **WHEN** the last clip frame is open
- **THEN** the stored clip runs to the end of the event clip and `clip_span` ends at its length

#### Scenario: Cut fails
- **WHEN** remuxing the clip raises a decode error
- **THEN** `clip_not_stored` is logged with `reason = "cut_failed"`, the door event has no `clip_key`, the stills are stored, and the outcome is still `door_open`

#### Scenario: Upload fails
- **WHEN** S3 rejects the `clip.mp4` upload
- **THEN** `clip_not_stored` is logged with `reason = "upload_failed"`, the door event has no `clip_key`, and analysis goes ahead

#### Scenario: No clip on the fallback path
- **WHEN** the clip is unavailable and the door check samples stills across the window
- **THEN** no `clip.mp4` is written and the door event has no `clip_key`

#### Scenario: Not a door opening
- **WHEN** the outcome is `not_door`
- **THEN** no `clip.mp4` is written

## MODIFIED Requirements

### Requirement: Clips never stored
The full event clip SHALL only be held in memory or in a temporary file in Lambda `/tmp`. The temporary file SHALL be deleted when the step ends, whether it succeeds or fails. The only clip object written to S3 SHALL be the open-span `clip.mp4` of a door opening. Apart from that clip, the stored stills and the debug-trace frames, no frame SHALL be written to S3.

#### Scenario: Door opening processed
- **WHEN** a door opening is processed from a clip with debug traces off
- **THEN** the only S3 objects written are `still-<n>.jpg` and one `clip.mp4`, and `clip.mp4` is shorter than the event clip

#### Scenario: Temporary file removed on error
- **WHEN** decoding fails partway through the clip
- **THEN** the temporary clip file no longer exists after the step

#### Scenario: Temporary file removed after the cut
- **WHEN** a door opening's clip is cut and stored
- **THEN** neither the downloaded clip nor the cut leaves a file behind in the clip directory
