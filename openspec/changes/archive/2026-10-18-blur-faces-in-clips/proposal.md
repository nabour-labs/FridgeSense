# Proposal

## Why

Each door opening's clip (`clip.mp4`) plays on Activity and in the Reference images clip picker exactly as Ring recorded it, faces included. That's why the clip is hidden from viewers. Stills already have faces blurred before storage. Clips should get the same treatment: blur only the face areas, and leave the fridge and the items in it sharp, so Nova and people can still see them.

Tracks: AWS Builder (Lambda container image, Step Functions, S3), Open Source (`deface`).

## What Changes

- New **clip blur step** after the door event is saved: a container-image Lambda uses the open-source `deface` detector (CenterFace, ONNX) to find faces in every frame of the open-span clip. It blurs an ellipse over each face, enlarged 30% about its centre, and re-encodes as H.264 MP4 that plays in browsers. Pixels outside face areas are left as they were, apart from re-encoding noise.
- While face blurring is on, the pipeline stores the cut as a private, short-lived `clip-raw.mp4`. The door event gets no `clip_key` until the blurred `clip.mp4` is written and the raw object is deleted. If blurring fails or times out, the clip is dropped: no `clip_key` is set, the raw object is deleted, and `clip_not_stored` is logged with `reason = "blur_failed"`. Activity then shows the stills, as it does today for a missing clip. This fails closed.
- While face blurring is off, nothing changes: `clip.mp4` is stored as cut and is never shown to viewers.
- `GET /api/events` returns the clip to viewers too when it is face-blurred (`clip_blurred = true` on the door event).
- The Reference images clip picker only ever plays clips from `GET /api/events`, so while blurring is on it shows blurred clips. The frame it grabs still goes through `POST /api/camera/frame` as well.
- The stills bucket gets a lifecycle rule that expires objects tagged `transient=true` after 1 day, as a backstop for raw clips that a crashed run leaves behind.
- The cost of each clip blur is logged (`clip_blur_cost`: Lambda GB-seconds as USD, frames, frames with faces).

## Out of scope

- Livestream (never blurred; owner-only after `owner-only-livestream`).
- Local dev clips in the Mock video picker (`tmp/*.mp4`, never deployed).
- Re-blurring clips stored before this change: they expire within 7 days.
- Changing how stills are blurred (Rekognition, already limited to face boxes).

## Capabilities

### New Capabilities

- `clip-face-blur`: blurring faces in a door opening's clip after it is cut. Covers the detector, face-area-only blurring, the output format, fail-closed handling, raw-clip cleanup and cost logging.

### Modified Capabilities

- `door-event-detection`: "Open-span clip stored" (raw clip while blurring is on) and "Clips never stored" (the transient raw clip).
- `inventory-api`: "Door event listing" (viewers get blurred clips).
- `inventory-app`: adds "Clip picker plays face-blurred clips".

## Impact

- New Python project `clipblur/` (`pyproject.toml`, `Dockerfile`, handler, tests). It depends on `deface` (installed without its `opencv-python` dependency), `opencv-python-headless`, `onnxruntime`, `av` and `numpy`.
- `infra/lib/door-pipeline.ts`: a `DockerImageFunction` (arm64, 10240 MB, 5 min, 2 GB ephemeral storage), `BlurClip` and `DropRawClip` states, and the lifecycle rule. The deploy needs Docker Desktop running on the Mac. It's installed, but the daemon was off when checked.
- Backend: `door_events.store_open_clip`, a `drop_raw_clip` task in `handlers/pipeline.py`, and `get_events` in `handlers/api.py`.
- README: the Blur faces and Activity sections.
- Depends on `face-blur-setting` (implemented, not yet archived). Archive it before this change.
