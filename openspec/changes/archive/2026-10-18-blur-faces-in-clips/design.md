# Design

## Context

- `door_events.store_open_clip` remuxes the open span with PyAV (no re-encode) and uploads `clip.mp4` during the `FetchStills` step. The door event gets `clip_key` and `clip_span` right away.
- All backend Lambdas share one zip, bundled locally with uv (no Docker). It already holds PyAV and Pillow and is near the 250 MB unzipped limit. Adding onnxruntime and OpenCV would go over it.
- Workflow: `FindWindow → FetchStills → (door_open) Analyze → Save → Done`, with errors going to `MarkFailed → AnalysisFailed`.
- The face-blur setting (`face_blur.load`) is read once per motion in `FetchStills` and passed as `face_blur` in the state.
- `deface` (ORB-HD/deface, MIT) bundles the CenterFace ONNX model. Its library exposes `CenterFace` (returns boxes and scores) and `anonymize_frame` (draws an ellipse blur per box, with `mask_scale` 1.3 by default). Its own CLI does I/O with imageio-ffmpeg and depends on `opencv-python`, which needs `libGL`, and the Lambda base image doesn't have it.

## Goals / Non-Goals

**Goals:** blur faces only, fail closed, keep the main pipeline zip untouched, and don't delay analysis.

**Non-Goals:** GPU, live video, and re-blurring old clips.

## Decisions

1. **Separate container-image Lambda (`clipblur/`).** Base image `public.ecr.aws/lambda/python:3.13-arm64`. It installs `deface==1.5.0 --no-deps` plus `opencv-python-headless`, `onnxruntime`, `scikit-image`, `numpy` and `av`. It's built with CDK `DockerImageFunction` (`Platform.LINUX_ARM64`), with 10240 MB memory (about 6 vCPU), a 5 min timeout and 2048 MB ephemeral storage. Its own `pyproject.toml` has pytest in the dev group, so CI runs its tests.
2. **Our own Python script, not the deface CLI.** `clipblur/blur.py` decodes with PyAV and runs `CenterFace` per frame. Detection uses a copy downscaled to at most 960 px wide, for speed, with boxes scaled back, on onnxruntime's CPU provider (measured on a real 2560×1440 Ring clip: 0.07 s per frame at 960 px against 0.10 s at 1280 px, while the Mac's default CoreML provider took 0.8 s). It calls `deface.anonymize_frame(..., replacewith="blur", ellipse=True, mask_scale=1.15)` on the full-size frame. deface grows each side by `mask_scale − 1`, so 1.15 gives the spec's 30% about the centre and encodes H.264 `yuv420p` with `+faststart` through PyAV. The detector is injected, so tests use a fake detector with fixed boxes and never need the model or real faces. This also keeps the same frame count and rate.
3. **Blur after `Save`.** Analysis and inventory don't wait for the clip. While the clip is pending, the event lists with `clip: null`, so Activity shows stills, and the next poll shows the video.
4. **Raw clip in S3, never linked.** The pipeline Lambda uploads `clip-raw.mp4` with `Tagging=transient=true`. The blur Lambda reads it, writes `clip.mp4`, and updates the event conditionally (`attribute_exists(pk)`), setting `clip_key`, `clip_span` and `clip_blurred`. Only then does it delete the raw clip. On any exception it deletes the raw clip and any partial clip, logs `blur_failed` and re-raises, so the Step Functions catch also records it. A tagged 1-day lifecycle rule backs up crashes and the `MarkFailed` path, where the raw clip is left behind.
5. **The `DropRawClip` catch is a pipeline-Lambda task** (`drop_raw_clip`). It runs in the zip Lambda, so a timeout of the container Lambda is still cleaned up.
6. **Viewers see clips only when `clip_blurred`.** A clip stored while blurring is off stays hidden from viewers, as today.
7. **Explicit thread counts (after the first live run).** At 3008 MB a 19 s opening (466 frames at 2560×1440) took 211 s, and onnxruntime logged `Error in cpuinfo: failed to parse the list of possible processors`, so its thread pool size can't be trusted. The function now has 10240 MB (about 6 vCPU). The CenterFace session is built with `intra_op_num_threads` set to the CPUs in the process's affinity mask, and PyAV decodes with `thread_type = "AUTO"` and encodes with x264 `threads` set to the same count. Cost per clip stays about the same, because a shorter run at more GB means similar GB-seconds.
8. **Cost log** uses `context.get_remaining_time_in_millis()` against the start time for `billed_ms`, and the ARM price of 0.0000133334 USD per GB-s.

## Risks / Trade-offs

- [CenterFace misses some faces: profiles, partly hidden faces, motion blur] → threshold 0.2 (deface's default) and an enlarged ellipse. The README will say the clip blur is best effort, unlike the per-still Rekognition blur. The owner can still delete an event.
- [Docker needed for `cdk deploy`] → Docker Desktop is installed. Start it before deploying. The first build pulls about 300 MB.
- [Runtime about 30–60 s per 10 s clip at 15 fps] → the 5 min timeout, logged `duration_ms`, and a cost of about $0.001–0.002 per clip.
- [`deface --no-deps` misses a dependency] → a container smoke test (`docker run` with the Lambda runtime emulator on a local `tmp/` clip) before deploying. It runs locally only and is never committed.
- [Raw clip briefly in S3] → it's private, never presigned, tagged, and deleted by the step or within 1 day.

## Test strategy

- **Unit (clipblur, pytest):** synthetic clips are generated in the test with PyAV (checkerboard, 640×360, 30 frames, 15 fps) and a fake detector.
  - Scenarios: "Face in some frames", "Low score ignored", "One face blurred", "Two faces blurred", "Face at the frame edge", "No faces", "Same timing" (1920×1080, 120 frames), "Detector fails", "Decode error".
- **Integration (clipblur, pytest + moto S3/DynamoDB):** "Clip published", "Event deleted while blurring", the fail-closed cleanup, and "Cost logged" with a fake Lambda context.
- **Backend (pytest + moto):** in `test_door_events.py`, "Raw clip while blurring is on" plus every existing scenario of "Open-span clip stored", including both upload failures and "Door opening processed with blurring on". Also `drop_raw_clip`, and `test_api_events.py` for the listing scenarios.
- **Infra (Jest, CDK assertions):**
  - "Lifecycle rule synthesized".
  - The `DockerImageFunction` is arm64 with 10240 MB and 300 s.
  - The state machine definition has `Save → HasRawClip → BlurClip → Done` and the catch to `DropRawClip`.
  - The blur role can only read and delete `*/clip-raw.mp4`, write `*/clip.mp4`, and `UpdateItem` on the table.
- **PWA (Vitest):** `RecentClipPicker.test.tsx` for the three picker scenarios.
- **Manual (after deploy, with OK):** open the fridge once with a face in view and check that the clip on Activity is blurred only around the face. Add a friction-log entry for anything surprising.
- No test calls live Ring, AWS or Bedrock. The real CenterFace model is used only in the local container smoke test.
