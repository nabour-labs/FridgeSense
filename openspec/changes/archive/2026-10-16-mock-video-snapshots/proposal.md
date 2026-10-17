# Proposal

## Why

Setting up reference images, door references and the fridge area each need camera snapshots that show the right moment: door open, door closed, an item held up. A live snapshot only shows the fridge as it is right now, so Jayson has to stand at the fridge and time each one. He already has 12 real recordings of the fridge in `tmp/` (local only, gitignored). Taking snapshots from those clips on localhost makes the setup screens quick to build and test, and gives the same frames every time.

Tracks: Ring (faster iteration on the camera-snapshot setup flows), Open Source (developer tooling).

## What Changes

- **Debug mode on localhost:** when the PWA runs on the Vite dev server, it is always in debug mode. A thin "Debug" bar under the header shows a "Mock video" switch. The built PWA (production) has no debug mode, no bar and no switch.
- **Mock video switch:** off by default, and remembered in this browser. When it is on, every camera snapshot in the app comes from a recording instead of `POST /api/camera/snapshot`. That covers "Camera snapshot" in Reference images and "New snapshot" in Open/close detection and Fridge area.
- **Clip picker:** with the switch on, a snapshot opens a sheet with:
  - a clip dropdown listing the `.mp4` files in the local videos folder (default `<repo>/tmp`, or `FRIDGESENSE_VIDEOS`), newest first;
  - the clip with a scrubber;
  - "Use this frame", which returns that frame as the snapshot, and "Cancel".
  The frame is resized like a camera snapshot (at most 960 px wide, JPEG) and flows through the screen exactly as a camera snapshot would.
- **Livestream from a clip:** with the switch on, the Activity "Livestream" dialog plays a clip instead of opening a live view at the camera. It shows a clip dropdown (newest first) and a "Mock video" label, loops the clip, and never calls `POST /api/camera/live`. With the switch off, the dialog is unchanged.
- **Dev-server video routes:** the Vite dev server lists the clips and streams them (with range requests, so scrubbing works) under `/__dev/videos`. These routes exist only on the dev server, whether it uses the mock API (`FRIDGESENSE_MOCK`) or proxies to a deployed backend (`FRIDGESENSE_URL`).
- **Accepted trade-off:** frames from the clips are **not face-blurred**. When the dev server proxies to a deployed backend, saving a reference or door reference made from a clip uploads that unblurred frame, which can later be sent to Bedrock. Jayson accepted this; the picker shows a one-line notice saying so when the backend is not the mock.

## Out of scope

- A countdown or session limit for the mocked livestream (the clip just loops until the dialog closes).
- Feeding clips into the webhook → stills → Nova pipeline, or the backend snapshot route.
- Face blurring of clip frames.
- Committing clips or frames to the repo, or uploading clips anywhere.
- Debug mode on any deployed host, or a way to turn it on there.
- Formats other than `.mp4` (H.264), and folders other than the one configured.

## Capabilities

### New Capabilities

- `mock-camera-video`: debug mode on the local dev server, the Mock video switch, the dev-server clip routes, and taking camera snapshots and the livestream from local recordings in place of the camera.

### Modified Capabilities

None. The production snapshot and livestream behaviour (`inventory-app`, `camera-live-view`) does not change; the switch exists only on the dev server.

## Impact

- New `pwa/scripts/dev-videos.ts` (Vite dev-server plugin), registered in `pwa/vite.config.ts` for `serve` only.
- New `pwa/src/debug/` (debug mode flag, stored switch, `ClipPicker` sheet, frame grab), and a wrapper in `pwa/src/App.tsx` that swaps `cameraSnapshot` while the switch is on, plus the Debug bar.
- `pwa/src/components/LiveStream.tsx` renders a clip player in place of the WebRTC view while the switch is on.
- `App.tsx` `report` ignores a cancelled pick, so Cancel leaves each screen as it was.
- README: one short "Mock video (localhost)" note.
- No backend, infra, AWS or cost change.
