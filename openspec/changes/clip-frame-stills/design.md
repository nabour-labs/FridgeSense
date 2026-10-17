# Design

## Context

`fetch_stills` already decodes every clip frame at `DOOR_FRAME_INTERVAL_MS`, keeps each as a JPEG `Downloaded` (quality 90, full 2560×1440) and scores it. For an opening it picks up to 4 of them, then `stills_at` asks Ring for a still at each frame's `at_ms` and keeps the frame only when Ring fails. See proposal.md - Why for the evidence that Ring's still can show a different moment.

## Goals / Non-Goals

**Goals:**
- What Nova sees is exactly what the door check scored open.

**Non-Goals:**
- Changing the stills-sampling fallback, the open span, the picks or the open/close times.
- Measuring the exact Ring still offset.

## Decisions

- **Store the picked frames as they are.** `chosen` already holds the frames' JPEG bytes; use `d.data` on both paths and delete `stills_at`. Alternative considered: keep the Ring still but re-score it against the door rules and fall back to the frame when it scores closed. Rejected: the last pick is the first closed frame, so "scores closed" cannot tell a good still from a wrong one there; it costs 4 Ring calls per opening; and the frames are already the same resolution as Ring stills.
- Frames keep `FRAME_JPEG_QUALITY = 90`; the crop step re-encodes at 95 as today. No new setting.

## Risks / Trade-offs

- [Video frames can show compression artefacts or motion blur that a Ring still would not] → Same resolution; the door check already relies on these frames; Nova sees 4 of them, and a blurrier right moment beats a sharp wrong one.

## Migration Plan

Deploy the pipeline Lambda as usual (needs Jayson's OK). Rollback: redeploy the previous build. No data migration.

## Test strategy

- Unit/integration (pytest, `tests/test_fetch_stills_clip.py`): a generated door clip served through respx as the 303 `Location` (existing `serve_clip`), Ring still endpoint mocked with a distinct image so tests can tell a Ring still from a frame; S3 and DynamoDB through moto (`aws` fixture); face blurring through `FakeBlurrer`.
- Assert which offsets are stored by decoding each blurred still and checking its colour against the lit/closed frames, and assert the still endpoint's call count is 0.
- No live Ring, AWS or Bedrock calls.
