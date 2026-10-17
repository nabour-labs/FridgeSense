# Tasks

## 1. Cut the clip (backend, `clip_frames`)

- [x] 1.1 Write failing tests in `backend/tests/test_clip_cut.py` for "Clip cut to the open span" (start keyframe 4.0 s, lasts under 9.0 s, span `[0.5, 8.5]`), "Door still open at the end of the clip" and the decode error from "Cut fails", using a synthetic 2 s-GOP MP4 built in `tests/clip_video.py`. Verify that `uv run pytest tests/test_clip_cut.py` fails because `cut_clip` is missing
- [x] 1.2 Implement `clip_frames.cut_clip(path, open_ms, close_ms | None, out_dir) -> (Path, (start_s, end_s))` as a PyAV stream-copy remux with faststart, raising `ClipUnavailable("cut_failed")`. Verify that the 1.1 tests pass

## 2. Store the clip in the pipeline (backend, `door_events`)

- [x] 2.1 Write failing tests in `test_door_clip_store.py` (moto S3, stubbed Ring serving the synthetic clip) for "Clip cut to the open span" end to end (`clip.mp4` under the stills prefix, `clip_key` and `clip_span` on the door event), "Door opening processed" (only stills and one shorter `clip.mp4`), "Temporary file removed after the cut", "No clip on the fallback path" and "Not a door opening". Verify that they fail
- [x] 2.2 Keep the downloaded clip alive until the span is known (a context manager or callback around `clip_frames_checked`), cut and upload it in `fetch_stills`, and save `clip_key` and `clip_span` on the door event. Verify that the 2.1 tests pass and the existing `test_clip_*` and `test_door_*` tests stay green
- [x] 2.3 Write failing tests for "Cut fails" and "Upload fails" (log `clip_not_stored` with the reason, no `clip_key`, outcome still `door_open`, analysis goes ahead), then implement the best-effort `try/except`. Verify that they pass
- [x] 2.4 Update the "Clips never stored" scenario test so it allows exactly one `clip.mp4`, and keep "Temporary file removed on error" green. Verify with `uv run pytest -k "clip or door"`

## 3. Expose the clip (backend, API)

- [x] 3.1 Write failing API tests for "Recent event with a clip" (link with `#t=0.5,8.5` that downloads from moto), "Viewer gets no clip", "Event without a clip" and "Old event" (`clip: null`). Verify that they fail
- [x] 3.2 Add `clip` to `get_events`: presign `clip_key` for 15 min, append the `#t=` fragment, and return `null` for viewers, for events with no key and for events older than 7 days. Verify that the 3.1 tests and every `test_api_*` test pass

## 4. Play the clip (PWA)

- [x] 4.1 Add `clip: string | null` to `DoorEvent` in `pwa/src/api/types.ts` and update the test fixtures that build events. Verify with `npm run typecheck` (or `tsc --noEmit`)
- [x] 4.2 Write failing Vitest tests in `Activity.test.tsx` for "Clip instead of stills", "Clip without stills", "Clip fails to load", "Stills" (with `clip: null`) and "No stills" (no clip). Verify that they fail
- [x] 4.3 Implement the clip video in `EventCard` (muted, playsInline, controls, `preload="metadata"`, poster = first still, `aria-label="Door opening at <time>"`), falling back to `Stills` on `error`. Verify that the 4.2 tests pass
- [x] 4.4 Write failing tests for "Poll with fresh clip link" and "Clip appears", then extend the link cache to `{stills, clip, at}`, keyed on still count and whether there is a clip. Verify that they pass along with the existing stable-link tests

## 5. Wrap up

- [x] 5.1 Run the full suites and linters green: `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`, then `cd pwa && npm test && npm run lint`. Report the commands and their results
- [x] 5.2 Add a friction-log entry if PyAV remuxing or S3 presigning with media fragments caused friction (skip it if none) (no friction hit)
