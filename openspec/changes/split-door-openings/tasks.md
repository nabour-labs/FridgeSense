# Tasks

## 1. Split the open span

- [x] 1.1 Write failing tests in `backend/tests/test_open_spans.py` for "Short closed run stays inside the opening" and "Long closed run splits the opening": a gap of exactly 10 s splits, an opening runs to the end, no open frame gives no span. Run `uv run pytest tests/test_open_spans.py` and see them fail.
- [x] 1.2 Implement `open_spans(opened, times_ms, min_gap_ms=MIN_CLOSED_GAP_MS)` in `door_events.py` (keep `open_span` only if something else still uses it). Verify with `uv run pytest tests/test_open_spans.py` green.

## 2. One door event per opening

- [x] 2.1 Write failing tests in `backend/tests/test_fetch_stills_split.py` (synthetic clip `[(1000, 6000), (18000, 24000)]`, 30 s window) for "Two openings in one clip", "Brief closed run in one opening", "Stills from each opening", "Keys per opening", "Media from its own span only" (blur on: `clip-raw.mp4` and `analysis.mp4` per prefix), "Output for two openings", "Output for one opening", "Each opening has its own status" and "Two openings in a re-run". Add a stills-path test for "Two openings in one window". Run them and see each fail for the right reason.
- [x] 2.2 Refactor `_fetch_stills` to run the per-opening branch (picks, blurred stills, open clip, status, door-event item) once per span, with opening-k keys and prefixes. Write all door events and the claim in one transaction, and build the analysis video per opening. Return `openings`, with top-level fields from opening 1. Verify that 2.1 passes and that `tests/test_fetch_stills_clip.py`, `test_fetch_stills_task.py`, `test_door_clip_store.py`, `test_analysis_video_store.py` and `test_analyze_video.py` stay green.

## 3. Traces and trace lookup

- [ ] 3.1 Write failing tests for "Two openings traced" and "One opening traced" (`tests/test_door_traces.py`), and for "Trace by a later opening's id" (`tests/test_api_debug.py`).
- [ ] 3.2 Add `openings` to `DoorTrace` and `door.json`, and make the trace lookup drop a `#<k>` suffix. Verify 3.1 green.

## 4. Workflow runs each opening

- [ ] 4.1 Update `infra/test/pipeline.test.ts`: the state helper flattens Map iterator states. Add failing tests for "Openings run one at a time", for the iterator's Analyze/Save catches going to `MarkOpeningFailed` → `OpeningFailed`, and for "One opening fails" / "All openings succeed" (`CheckOpenings` → `AnalysisFailed` | `Done`). Run `npm test` in `infra/` and see them fail.
- [ ] 4.2 Add the sequential Map in `infra/lib/door-pipeline.ts`. Verify that `npm test` in `infra/` is green and that `npx cdk synth` succeeds (no deploy).

## 5. Clip evaluation

- [ ] 5.1 Write a failing test for "Openings separated by a long gap" (`tests/clips/`). Keep "Two openings in one clip" (9 s gap) as it is.
- [ ] 5.2 Make `expected_span` stop at the first labelled gap of 10 s or more. Verify `uv run pytest tests/clips` green.

## 6. Wrap-up

- [ ] 6.1 Run the full backend suite (`uv run pytest`), `uv run ruff check . && uv run ruff format --check .`, and `npm test` in `infra/`, all green. Add a friction-log entry only if a covered service caused friction.
