# Design

## Context

- `fetch_stills` (`backend/src/fridgesense/door_events.py`) downloads up to `MAX_STILLS = 30` Ring stills across the window (8 in parallel), scores each with `DoorCheck`, takes `open_span`, picks up to 4 stills, then crops, blurs, stores and records the DOOR item. It runs in the pipeline Lambda: arm64, 512 MB, 90 s timeout.
- The Ring clip download (`POST /v1/devices/{id}/media/video/download`, `{timestamp, duration}`) answers 303 with a temporary link, like stills. Clips are capped at 15 min, 1920×1080 and 1–25 fps. Footage from before the account was linked is refused (403). We have never called this endpoint. The request units (`duration` in ms or s) and whether frame rate can be requested are not confirmed.
- The clip harness (`backend/tests/clips/harness.py`) already decodes with PyAV and fakes Ring's still download with respx. Measured locally: a 125.6 s 2560×1440 clip decodes at 0.5 s spacing in 3.6 s, and the door check on 251 frames takes 1.9 s.
- The Lambda bundle is built by `uv pip install --python-platform aarch64-manylinux_2_28`. `av` 19.0.1 ships an abi3 `manylinux_2_28_aarch64` wheel (32.7 MB, FFmpeg bundled). Today's bundle is 53 MB unzipped.

## Goals / Non-Goals

**Goals:**
- Fixed frame spacing at any event length, using one Ring request.
- Today's still path kept, unchanged, as the fallback.

**Non-Goals:**
- Faster analysis. Nova still gets ≤4 stills.
- Splitting decode into its own Lambda or Step Functions state.

## Decisions

1. **Same step, clip first, stills as fallback.** `fetch_stills` tries the clip, and on any `ClipUnavailable(reason)` it runs the existing still-sampling code unchanged. No state machine change. *Alternative:* a new `FetchClip` state with a Choice. That makes a clearer graph for judges, but it means CDK and state-shape changes for no behaviour gain.

2. **New module `clip_frames.py`.** `download_clip(ring, http, device_id, start_ms, duration_ms, sleep) -> Path` streams to a `tempfile` under `/tmp` and stops past 300 MB. `sample_frames(path, offsets_ms) -> list[(offset_ms, PIL.Image)]` decodes one forward pass and keeps the latest frame with `pts ≤ offset`. This is the harness's `AvSource.prepare` logic, moved into the package so the tests and production share it. `import av` happens only inside these functions, so other Lambdas never load FFmpeg.

3. **Door check on PIL images, no JPEG round-trip.** `DoorCheck.zone_values` already accepts `Image.Image`. Frames are scored in memory. Only frames that might be stored (picked stills that failed to download, or trace frames) are encoded to JPEG (quality 90).

4. **Frames reuse the `Downloaded` shape.** Each frame becomes `Downloaded(n, at_ms, data)`, with `data` a lazily encoded JPEG for traces. So `open_span`, `pick`, `DoorTrace` and the trace writer work unchanged. Traces write `raw-<n>.jpg` per sampled frame, up to about 240 per 2-minute event, which is S3 PUTs worth well under a cent. They are already behind `DEBUG_TRACES`.

5. **Stills at picked frame times.** After `pick(span)`, `fetch_still` runs for each picked time, in parallel, with `STILL_RETRY_DELAYS_S`. A miss falls back to the frame's JPEG. The opening is already confirmed by the clip, so a missing still never turns it into `no_media` while the frame exists.

6. **Request body `{"timestamp": start_ms, "duration": end_ms - start_ms}` in ms**, as stills use ms timestamps. Task 1.1 confirms the units and any frame-rate option against one real response before the code relies on them. If Ring takes an fps option, request about 4 fps, which is enough for a 0.5 s spacing and makes downloads smaller.

7. **Lambda sizing: 2048 MB, 150 s timeout.** Decoding is CPU-bound, and 2048 MB gives about 1.2 vCPU. Even at 5× the local decode time (~28 s for 2 minutes), plus the download and ≤4 stills, the step stays well under 150 s. The fallback path's 90 s still budget fits inside 150 s.

8. **`av` becomes a runtime dependency.** It moves from the `clips` group into `[project].dependencies`. CI's `uv sync --dev` then installs it, so clip-decoding unit tests run in CI on a tiny generated MP4 (written with PyAV in a fixture). The real `tmp/` clips stay local.

## Test strategy

- **Unit (CI):**
  - `download_clip`: the request body; 303 with no auth on the link; 425/416 retries; 403 → `status_403`; network error; size cap, both by `Content-Length` and while streaming; temp file removed.
  - `sample_frames`: offsets on a generated MP4 with known coloured frames at known pts; latest frame ≤ offset; offset past the end; non-video bytes → `decode_failed`.
  - `parse_frame_interval`: default and invalid values.
- **Contract:** a recorded Ring clip-download 303 response (task 1.1) under `tests/fixtures/ring/`. The fake camera answers in exactly that shape.
- **Task level (CI):** `fetch_stills` with respx Ring and a generated MP4 behind the `Location`, plus moto S3/DynamoDB and `FakeBlurrer`. It covers every scenario in the spec delta: open/close times, picked still times, still-missing frame substitution, not-door with no still requests, and every fallback reason ending in today's still path, checked with the existing still-path assertions.
- **Integration (local, `-m clips`):** the clip harness's fake camera gains the clip route (serving the real file), so `evaluate_clip` and the report exercise the clip path. The report must still show 0 FP and 0 FN, and 2023 should now be detected.
- **Infra:** a CDK assertion test for the pipeline Lambda's memory, timeout and `DOOR_FRAME_INTERVAL_MS`.
- **Stubbed:** Ring (respx), S3/DynamoDB (moto), Rekognition (`FakeBlurrer`). No Bedrock.

## Risks / Trade-offs

- [Ring clip request shape differs from the plan's notes] → Task 1.1 records a real response first. The fallback keeps events working whatever happens.
- [Clips lag behind stills: a clip may not be ready when the window is] → 425/416 retries, then fallback to stills. The `clip_unavailable` reason counts in logs show how often this happens.
- [Lambda decode slower than estimated] → Log `clip_decode_ms` per event. Raising memory is a one-line CDK change.
- [Bigger bundle for every Lambda (shared asset)] → About 33 MB zipped, well under the limits. `av` is imported lazily, so other handlers' cold starts don't pay for it.
- [Fewer stills downloaded, so the trace no longer has raw Ring stills for not-door events] → Frames show the same scene. The fallback path still traces stills.

## Migration Plan

Deploy with `cdk deploy` (with Jayson's OK). There is no data migration. Rollback: redeploy the previous commit. Setting `DOOR_FRAME_INTERVAL_MS` doesn't disable the clip path, so rollback is by redeploy.
