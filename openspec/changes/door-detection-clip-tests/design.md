# Design

## Context

- The door check runs inside `fetch_stills` (`backend/src/fridgesense/door_events.py`). It asks Ring for one still per `STILL_INTERVAL_MS` across the event window (`still_times`/`still_count`). It scores each still with `DoorCheck` and takes the open span (`open_span`). That span sets `opened_at`/`closed_at` on the DOOR item.
- `test_fetch_stills_task.py` already fakes Ring with respx: the download POST is answered with a 303 redirect, and the redirect GET returns image bytes. S3 and DynamoDB come from moto (the `aws` fixture), and faces from `FakeBlurrer`.
- The 12 clips in `tmp/` are 2560×1440 MP4s, 3–24 MB each. `tmp` and `*.mp4` are git-ignored.
- ffmpeg is not installed on the dev Mac. CI runs `uv sync --dev` + `uv run pytest` in `backend/`.

## Goals / Non-Goals

**Goals:**
- Exercise the real `fetch_stills` path end to end on real footage, with no code path that exists only for tests.
- Have one number to watch (the confusion matrix plus timing error) when tuning zones, the threshold or the interval.

**Non-Goals:**
- Making Ring's still compression bit-exact. Clip frames are a close stand-in, not a replica.
- Running in CI (the videos are private and too large).

## Decisions

1. **Fake camera at the HTTP layer (respx), not a new seam in `door_events`.** The fake answers the same download POST and redirect GET that the existing tests mock. It looks up the frame by the `timestamp` in the request body. `download_all_stills`, `still_times`, retries, `open_span` and the DOOR item all run unchanged. *Alternative:* factor a pure `detect(stills, times)` out of `fetch_stills` and call it directly. That is simpler, but it would skip the sampling and timing code we want to measure, and it means a refactor. We can still do it later if the report needs speed.

2. **PyAV for decoding, in its own `clips` dependency group.** `av` ships wheels with FFmpeg bundled, so nothing needs to be installed system-wide. CI's `uv sync --dev` does not install it, so CI stays fast and the tests skip there (`pytest.importorskip`). *Alternatives:* opencv-python-headless is a heavier wheel with a cruder seek. Shelling out to ffmpeg doesn't work because it is not installed.

3. **Decode once per clip, then serve from memory.** Each clip is decoded once to a sorted list of `(pts_seconds, PIL.Image)` at the sample times needed, or at every 100 ms step for the sweep. A request for `t` gets the latest frame with `pts ≤ t`, encoded as JPEG (quality 90). The cache is keyed by clip and lives in a session-scoped fixture or module cache, so the report's sweep does not decode again. Memory use is bounded by keeping only the frames at the requested times, not every decoded frame.

4. **Window = fixed epoch + clip duration.** `start_ms = 1786715596000`, `end_ms = start_ms + duration_ms`, and `ring_event_id = "clip-<name>"`. A Ring recording starts at the motion event, so this matches the real window shape.

5. **Labels are seconds from the clip start, in JSON next to the other fixtures.** Several openings in one clip collapse to first open → last close in the test. That is what `open_span` produces today, and it keeps the test honest about current behaviour. The report flags these clips so that merged openings are visible.

6. **Tolerance 1.5 × interval.** Detected open is the first open still, which is up to one interval after the true open. Detected close is the first closed still after, up to one interval after the true close. The extra 0.5 interval covers labelling error and frame timing.

7. **Shared core for tests and report.** A small module `backend/tests/clips/harness.py` holds the label loader, clips-folder resolution, fake camera and `evaluate_clip(...) -> ClipResult`. The test file and `scripts/door_clip_report.py` both import it, so the report scores exactly what the tests assert. The report adds `backend/` to `sys.path`, as the existing script does.

8. **Network guard.** The harness runs inside `respx.mock(assert_all_mocked=True)`, so any request the fake does not handle raises. moto covers S3 and DynamoDB, as in the `aws` fixture.

## Test strategy

- **Unit (always run, in CI):** the label loader (valid, close before open, overlap, negative or missing time, null not last). The expected-span calculation (merge, null close). Tolerance and verdict scoring, including failure messages. Report summary maths and the confusion matrix from canned `ClipResult`s. Sweep and `--dump-dir` argument validation. The `git check-ignore` check on a clip path.
- **Fake camera (in CI, no decoder):** the frame source is an interface, so a stub source of solid-colour frames tests the frame-at-time lookup, 404 past the end, and redirect flow without PyAV.
- **Integration (`-m clips`, local only):** one parametrized test per labelled clip over the real videos. Skips cover a missing folder, a missing clip and a missing `av`. An unreadable clip is checked with a small text file renamed `.mp4` in a temp clips folder.
- **Fixtures:** `backend/tests/fixtures/clips/door_labels.json` (real labels). Unit tests write their own small label files in `tmp_path`.
- **Stubbed:** Ring (respx), S3 and DynamoDB (moto), face detection (`FakeBlurrer`). Nothing calls Bedrock.

## Risks / Trade-offs

- [Clip frames are not Ring stills: different compression and maybe resolution] → Note it in the report header. If the numbers look odd, compare one Ring still against the clip frame at the same moment before tuning on clip results alone.
- [Labels are subjective by about half a second] → Label at the moment the light or interior first shows and the moment the door seals. The tolerance absorbs the rest.
- [12 clips is a small sample, and all from one evening's lighting] → The report is for direction, not proof. Add clips from day and night as they come.
- [Decoding 2560×1440 video is slow] → Decode only the sample times, and cache per clip across the sweep.
- [Default zones were measured on one of these same clips] → Expect optimistic numbers. Call it out in the report, and hold out new clips when they come.

## Migration Plan

None. These are dev-only files with no deployment.
