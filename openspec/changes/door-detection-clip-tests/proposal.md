# Proposal

## Why

The door check (which zone shows the lit fridge, the open span, opened/closed times) is only tested on synthetic coloured JPEGs. We now have 12 real fridge recordings in `tmp/` (Oct 15, 2026). Nothing tells us how often the check gets real openings right, or how far off its open/close times are. We need that before the demo, and every time someone tunes zones, the threshold or the still interval.

## What Changes

- A labels fixture, committed: for each recorded clip, the openings a person saw (seconds from clip start, opened and closed) or none. It stores labels only. The videos stay in `tmp/` and are never committed or uploaded.
- A fake camera for tests. It answers the still-download requests the pipeline already makes with the clip frame at the requested timestamp, so the real still sampling and door check run unchanged.
- Clip integration tests, one per labelled clip. Each checks door vs not-door and the opened/closed times within a tolerance. They skip (with a reason) when the clips or the video decoder are missing, so CI and fresh checkouts skip them.
- A local accuracy report command: confusion matrix, per-clip timing errors, and a sweep over threshold and still interval values. It can optionally dump the sampled stills with their zone values into `tmp/` to help with labelling.
- A new optional dev dependency group for the video decoder (PyAV). The default `dev` group and CI stay unchanged.

Out of scope: changing the door check itself (tuning comes later, from what the report shows), per-device setup rules from door references (`door-zone-setup`), detecting several separate openings in one window, Nova analysis on clips, and anything deployed to AWS.

Hackathon tracks: Ring (accuracy of the open/close detection built on the Ring Indoor Cam), Open Source (a repeatable way for others to check detection on their own recordings).

## Capabilities

### New Capabilities
- `door-clip-evaluation`: measures the door open/close check against labelled local fridge recordings, both as skippable integration tests and as a local accuracy report.

### Modified Capabilities
None. The door check's behaviour (`door-event-detection`) does not change.

## Impact

- New: `backend/tests/fixtures/clips/door_labels.json`, `backend/tests/clips/` (fake camera and tests), `backend/scripts/door_clip_report.py`.
- `backend/pyproject.toml`: a `clips` dependency group (`av`) and a registered `clips` pytest marker.
- No production code, infrastructure or API changes. No live Ring, AWS or Bedrock calls: S3 and DynamoDB use moto, and face blurring uses the existing fake blurrer.
