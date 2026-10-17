# Proposal

## Why

A reference image works best when it shows the item where it actually sits in this fridge. "Camera snapshot" only shows the fridge right now, usually with the door closed, so the item can't be seen. Each door opening's clip, which `event-open-clip` stores, shows the item while it goes in or comes out. On the dev server, "Mock video" already lets the owner scrub a clip and use a frame for the snapshot. This change gives the deployed app the same picker, fed by the recent door-opening clips.

Hackathon tracks: **Ring** (reuses Ring event video for setup) and **AWS Builder** (S3 CORS, presigned links).

## What Changes

- "Add a reference" gets a third source, "Recent clip", next to "Choose photo" and "Camera snapshot".
- "Recent clip" opens the "Snapshot from a recent clip" sheet. A dropdown lists the door openings from the last 7 days that have a clip, newest first, labelled with the day, time and duration (for example "Today 18:02 · 25 s"). The selected clip plays with a scrubber. "Use this frame" grabs the frame on screen and sends it to `POST /api/camera/frame`, which blurs any faces. Only the blurred image comes back and is shown for drawing. "Cancel" closes the sheet.
- The video, scrubber and buttons are shared with the dev-only Mock video picker, which keeps its own behaviour.
- The stills bucket gets a CORS rule that allows `GET` and `HEAD` from any origin. Without it the browser can't draw the S3 video onto a canvas. Access still needs a 15-minute signed link.
- "Camera snapshot" and the Open/close detection and Fridge area snapshots are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `inventory-app`: "Manage reference images" gains the "Recent clip" source and its picker.
- `door-event-detection`: the stills bucket lets browsers read signed links cross-origin.

## Out of scope

- Recent clips in Open/close detection and Fridge area. They need a closed or empty fridge, which the live snapshot gives.
- Clips older than 7 days, clips from the still-sampling fallback, and any clip `event-open-clip` doesn't store.
- Viewers. They can't add references, and the API never gives them clips.
- Picking a frame on the server, or storing the picked frame anywhere but the reference.
- Fire TV and MCP.

## Impact

- PWA: `screens/ReferenceImages.tsx`, the shared frame picker split out of `debug/ClipPicker.tsx`, and a new `camera/RecentClipPicker.tsx`.
- Infra: a CORS rule on the stills bucket in `infra/lib/door-pipeline.ts`.
- Backend: no changes. It reuses `GET /api/events` (with `clip`) and `POST /api/camera/frame`.
- Depends on `event-open-clip`, which must be merged first.
- Cost: one Rekognition face check per picked frame, the same as a live snapshot.
