# Design

## Context

`event-open-clip` makes `GET /api/events` return `clip`, a 15-minute presigned link to the open-span `clip.mp4` with a `#t=start,end` fragment. Viewers always get `null`. The dev-only `ClipPicker` (`debug/ClipPicker.tsx`) already has the video, scrubber and "Use this frame" UI, and `grabFrame` (`image.ts`) draws the shown frame into a JPEG at most 960 px wide. `POST /api/camera/frame` blurs faces in an app-sent frame and returns `{image, captured_at}`, as a live snapshot does. The stills bucket has no CORS rule.

## Goals / Non-Goals

**Goals:**
- Pick any moment of a recent door opening as a reference image.
- Never show or upload an unblurred frame. Only the image `POST /api/camera/frame` returns reaches the drawing step.
- Reuse the Mock video picker UI instead of building a second one.

**Non-Goals:**
- Changing how "Camera snapshot" works, or the Mock video switch.
- Any backend route.

## Decisions

1. **A third source button, not a step inside "Camera snapshot".** "Camera snapshot" stays one tap, and its live-view and fallback scenarios stay the same. "Recent clip" is a separate button in the same row. *Alternative considered:* turning "Camera snapshot" into a chooser between live and clips. That adds a tap to every snapshot and changes three screens. Rejected.

2. **Split `FramePicker` out of `ClipPicker`.** `FramePicker({title, clips, empty, notice, crossOrigin, onFrame, onCancel, grab})` holds the select, video, scrubber and buttons. `ClipPicker` (dev clips from `/__dev/videos`) and `RecentClipPicker` (door openings from `api.events(7)`) are thin wrappers that build the clip list. `onFrame` gets the base64 frame. Each wrapper decides what to do next: `ClipPicker` returns it as-is, and `RecentClipPicker` sends it to `cameraFrame`.

3. **Clip list from `api.events(7)`.** The picker keeps events with a non-null `clip`, newest first. A label is `dayLabel(opened_at)` + `clock(opened_at)` + ` · <duration_s> s`. The dropdown value is the event id, so a poll with a fresh link can't change the selection. The picker loads once when it opens and doesn't poll. It closes long before the 15-minute link expires.

4. **`crossOrigin="anonymous"` + bucket CORS.** Drawing a cross-origin video onto a canvas taints it, and `toBlob` then throws `SecurityError`. The recent-clip video sets `crossOrigin="anonymous"`. The stills bucket allows `GET` and `HEAD` from origin `*`, with `Range` among the allowed headers, because video requests use byte ranges. *Why `*`:* the stack builds the bucket before the CloudFront distribution, and the API Lambda that the distribution fronts references the bucket. Naming the distribution's domain would make a dependency cycle. CORS isn't access control here: every object needs a 15-minute signature. The dev server (`localhost:5173`) also works with `*`.

5. **The `#t=` fragment stays on the source.** The video starts at the moment the door opened. The scrubber still covers the whole stored cut, so the owner can step a little before or after.

6. **Errors.** The video fails to load → "This clip can't be played", and "Use this frame" is disabled (same as `ClipPicker`). `grab` throws (for example, a tainted canvas) → "This frame can't be used. Try another clip.". `cameraFrame` answers 502 → "Faces couldn't be blurred, so this frame can't be used." Other errors go to `report`. The sheet stays open after an error.

## Risks / Trade-offs

- [The CORS rule is broad] → It only lets browsers read responses to requests that already carry a valid signature. It grants no access by itself.
- [Safari caches a non-CORS response for the same URL] → The Activity card's video doesn't set `crossOrigin`. The picker fetches its own fresh list of links, so the URLs differ (new signature).
- [No recent clips until `event-open-clip` has run for a while] → The sheet says "No door openings with a clip in the last 7 days." and "Use this frame" is disabled.

## Migration Plan

Deploy `event-open-clip` first (or together). The CORS rule is additive. Rolling back the PWA just removes the button.

## Test strategy

- **Component (Vitest, jsdom):** `RecentClipPicker.test.tsx` uses a fake `api.events` and `api.cameraFrame` and a stub `grab`. It covers the list order and labels, events without a clip left out, the empty state, video `crossOrigin` and `src`, a load error, "Use this frame" sending the grabbed frame to `cameraFrame` and returning only the blurred image, a 502 message, a grab failure message, and Cancel making no request. `Config.test.tsx` covers the "Recent clip" button end to end in the reference sheet: the picked frame is shown for drawing and saved at 768×432. It also checks that the button is absent for viewers, since they get no Add button.
- **Regression:** the existing `ClipPicker.test.tsx`, `ClipLive.test.tsx` and reference-image tests stay green unchanged after the `FramePicker` split.
- **Infra (Vitest, CDK assertions):** `pipeline.test.ts` asserts the stills bucket's `CorsConfiguration` (GET/HEAD, origin `*`, `Range` header allowed, the length and range headers exposed).
- **Stubbed:** all API calls (fake `Api`), frame grabbing (stub `GrabFrame`). Nothing calls live Ring or AWS.
- **Manual:** after deploy, add a reference from a recent clip on the hosted PWA and check that a face in the frame comes back blurred.
