# Proposal

## Why

The door check samples Ring stills, and each still is a separate download. So it is capped at 30 stills per event, which means 3–4 s gaps on 2-minute events. On the local clips that cap missed a real ~3 s opening (clip 2023, 63.7–66.7 s). It also adds about 0.5–4 s of error to open/close times. Downloading the event's clip once and checking a frame every 0.5 s gives the same spacing at any event length, with one Ring request.

## What Changes

- The fetch-stills step downloads the event clip once (`POST /v1/devices/{id}/media/video/download`, same 303 flow as stills) and runs the door check on a decoded frame every `DOOR_FRAME_INTERVAL_MS` (default 500 ms) across the whole window.
- The open span and `opened_at`/`closed_at` come from those frames. The door rules are unchanged: default zones, threshold and per-device setup rules all apply as before.
- For a door opening, up to 4 Ring stills are still downloaded, at times picked from the open span, because stills are sharper than video frames. A still that can't be downloaded is replaced by its clip frame. Cropping, face blurring, storage and analysis are unchanged.
- If the clip can't be fetched or decoded, the step falls back to the current still sampling and logs why. A door opening is never dropped because of the clip.
- PyAV becomes a runtime dependency, and the pipeline Lambda gets more memory and time for decoding.
- The clip is processed in memory and in Lambda `/tmp` only. It is never stored in S3.
- Debug traces store the sampled frames in place of the sampled stills.

Out of scope: sending the clip to Nova, storing clips, re-tuning the threshold or zones, a separate step or Lambda for decoding, the PWA (it shows door events as before), and fixing clip 2023's label. The label fix is a separate small change, so the clip report shows the gain.

Hackathon tracks: Ring (uses the Ring clip download API, more accurate open/close detection from the Ring Indoor Cam), AWS Builder (Lambda video decoding in the Step Functions workflow).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `door-event-detection`: adds a door check on frames from the event clip, with still sampling as the fallback. The door rules, door event record, face blurring and storage stay as specified.

## Impact

- `backend/src/fridgesense/door_events.py` (clip download, frame sampling, still picking, fallback). New module `backend/src/fridgesense/clip_frames.py` (PyAV decoding). `traces.py` (frames in door traces).
- `backend/pyproject.toml`: `av` moves from the `clips` group to runtime dependencies.
- `infra/lib/door-pipeline.ts`: pipeline Lambda memory 512 → 2048 MB, timeout 90 → 150 s, new `DOOR_FRAME_INTERVAL_MS` setting. The Lambda bundle grows by about 33 MB zipped, still under the 250 MB unzipped limit.
- `backend/tests/clips/harness.py`: the fake camera also serves the clip download, so the clip tests and report exercise the new path.
- Cost: one clip download per motion event, about 25 MB for 2 minutes at 1080p. Fewer still downloads (≤4 instead of up to 30). Longer, larger Lambda runs on motion events only. Nova, face detection and S3 storage per opening are unchanged.
