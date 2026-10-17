# Tasks

## 1. Ring clip contract and dependency

- [x] 1.1 With Jayson's OK, make one real `POST /v1/devices/{id}/media/video/download` for a recent motion event (a read of existing footage). Record the 303 response (redacted `Location`) as `backend/tests/fixtures/ring/video_download_303.json`, and note the confirmed `duration` units and any fps option in design.md. Add a friction-log entry if the docs and the behaviour differ. Verify that the fixture loads in `test_fixtures.py`.
- [x] 1.2 Move `av` from the `clips` group to runtime dependencies in `backend/pyproject.toml` and update `uv.lock`. Verify that `uv sync && uv run pytest` is green and `uv export --no-dev` lists `av`.

## 2. Clip download

- [x] 2.1 Write failing tests in `tests/test_clip_download.py` for the scenarios One clip request per event (body), Clip link gets no token, Clip not ready yet, Ring refuses the clip, Clip never ready, Network error, Clip too large (by `Content-Length` and while streaming), and Temporary file removed on error (download part). Confirm red.
- [x] 2.2 Implement `download_clip` in `backend/src/fridgesense/clip_frames.py` (streams to `/tmp`, raises `ClipUnavailable(reason)`). Verify the 2.1 tests pass.

## 3. Frame sampling

- [x] 3.1 Add a test helper that writes a tiny MP4 with PyAV (solid-colour frames at known pts). Write failing tests for the scenarios Frame every 500 ms, Frame shown at an offset, Interval from config, Invalid interval, Unreadable clip (`decode_failed`), and Temporary file removed on error (decode part). Confirm red.
- [x] 3.2 Implement `sample_frames` and `parse_frame_interval` (lazy `import av`). Verify the 3.1 tests pass.
- [x] 3.3 Refactor `tests/clips/harness.py` `AvSource` to use `sample_frames`. Verify that `uv run pytest tests/clips` is green.

## 4. Door check from the clip in fetch_stills

- [x] 4.1 Write failing task-level tests in `tests/test_fetch_stills_clip.py` (respx Ring serving a generated MP4, moto, `FakeBlurrer`) for the scenarios Not a door opening, Open and close times, Still open at the end of the clip, Four stills from the open span, Short open span, Still missing frame used, and Door opening processed (no `.mp4` in S3). Confirm red.
- [x] 4.2 Implement the clip path in `fetch_stills` (frames as `Downloaded`, `open_span`/`pick` reused, stills at picked times, frame fallback, `clip_decode_ms` logged). Verify that the 4.1 tests and the existing `test_fetch_stills_task.py` pass.
- [x] 4.3 Write failing tests for the fallback scenarios at task level (Ring refuses the clip, Clip never ready, Unreadable clip, Clip too large, Network error): each logs `clip_unavailable` with its reason and then behaves exactly like today's still path. Implement the fallback wiring and verify the tests pass.
- [x] 4.4 Read `DOOR_FRAME_INTERVAL_MS` in `handlers/pipeline.py` (validated before any Ring request), and make sure door traces write sampled frames. Write the handler test first, then verify `uv run pytest` is green.

## 5. Local clip evaluation on the new path

- [x] 5.1 Give the harness fake camera a clip-download route that serves the real local file, and switch `evaluate_clip` to the clip path. Write a failing test (stub source) for the scenario Short opening between stills, then make it pass. Verify that `uv run --group clips pytest -m clips` runs.
- [x] 5.2 Run `uv run --group clips python scripts/door_clip_report.py` and record the results in this change. 2023's opening should now show as detected; it will read FP until its label is fixed. There must be no new FN.

## 6. Infrastructure

- [x] 6.1 Write a failing CDK assertion in `infra/test/pipeline.test.ts`: pipeline Lambda `MemorySize 2048`, `Timeout 150`, `DOOR_FRAME_INTERVAL_MS` in its environment. Then update `infra/lib/door-pipeline.ts` and the stack props. Verify that `cd infra && npm test` is green and `cdk synth` succeeds with the bigger bundle (check the asset size stays under 250 MB unzipped).

## 7. Docs and integration check

- [x] 7.1 Update the README pipeline description (clip-based door check, still fallback, `DOOR_FRAME_INTERVAL_MS`). Verify that the documented setting matches the CDK default.
- [x] 7.2 Run the full `uv run pytest`, `uv run ruff check . && uv run ruff format --check .` in `backend/`, and `npm test` in `infra/`. Verify all are green. Deploying (`cdk deploy`) needs Jayson's OK and is not part of this task.
