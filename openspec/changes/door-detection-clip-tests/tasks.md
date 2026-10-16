# Tasks

## 1. Setup

- [x] 1.1 Add a `clips` dependency group (`av`) to `backend/pyproject.toml`, register the `clips` pytest marker, and create `backend/tests/clips/__init__.py`. Verify that `uv sync --group clips` installs and `uv run python -c "import av"` works, and that `uv run pytest` is still green without the group.

## 2. Labels fixture

- [x] 2.1 Write failing tests for the scenarios Valid labels load, Close before open, Overlapping openings, Negative or missing time, and Only one opening may stay open (`tests/clips/test_labels.py`). Run them and confirm they fail because there is no loader yet.
- [x] 2.2 Implement the label loader in `tests/clips/harness.py` so that the 2.1 tests pass.
- [x] 2.3 Write failing tests for expected-span calculation (scenarios Two openings in one clip and Door still open at clip end, span part only), then implement it. Verify the tests pass.

## 3. Clip camera

- [x] 3.1 Write failing tests, using a stub frame source of solid-colour frames, for the scenarios Frame at the requested time and Request past the end of the clip. They cover the redirect flow and a 404 that is recorded as a missing still. Confirm red.
- [x] 3.2 Implement the fake camera (respx routes on top of a frame-source interface) so that the 3.1 tests pass.
- [x] 3.3 Write failing tests for the scenarios Clips folder from the environment and Videos ignored by git (`git check-ignore`). Then implement clips-folder resolution and verify the tests pass.
- [x] 3.4 Implement the PyAV frame source (decode only the requested times, cache per clip). Write a failing test for the Unreadable clip scenario (text file renamed `.mp4`, skipped if `av` is missing), then make it pass.

## 4. Per-clip evaluation and tests

- [x] 4.1 Write failing tests for `evaluate_clip` scoring with a stub frame source: Opening found with correct times, Open time too far off, Missed opening, False opening, No opening none detected, Door still open at clip end, Shorter still interval (tolerance 0.75 s, roughly 500 ms request spacing) and Long clip hits the still cap. Check the failure-message contents. Confirm red.
- [x] 4.2 Implement `evaluate_clip` (window = epoch + duration, runs the unchanged `fetch_stills` with moto + `FakeBlurrer` inside `respx.mock(assert_all_mocked=True)`). Verify the 4.1 tests pass.
- [x] 4.3 Write a failing test for the Network blocked scenario: a request the fake camera doesn't handle must raise. Then make it pass.
- [x] 4.4 Add `tests/clips/test_door_clips.py`: one `clips`-marked test per label entry. Write tests for the scenarios Fresh checkout or CI, One labelled clip missing, Decoder not installed, and Run only the clip tests (pytester or a subprocess run with a temp clips folder and labels). Verify that `uv run pytest` reports clip tests as skipped and `uv run pytest -m clips` selects only them.

## 5. Label the real clips

- [x] 5.1 Implement `--dump`/`--dump-dir` in `scripts/door_clip_report.py`, test first: scenarios Dump stills (stub source, temp `tmp/`) and Dump outside tmp refused. Verify the tests pass.
- [ ] 5.2 Run `uv run python scripts/door_clip_report.py --dump` on the 12 clips. Draft `backend/tests/fixtures/clips/door_labels.json` from the dumped stills, and have Jayson confirm or correct every clip's opened and closed times. Verify that the file loads with the 2.2 loader.

## 6. Accuracy report

- [ ] 6.1 Write failing tests for the scenarios Report over all clips (canned results giving `TP 1  FP 0  FN 1  TN 1`, open error 0.4 s), No clips present, and Unlabelled clips listed. Then implement the report rows and summary. Verify the tests pass.
- [ ] 6.2 Write failing tests for the scenarios Sweep two thresholds and two intervals (four rows, each clip decoded once) and Bad sweep value (non-zero exit before decoding). Then implement the sweep. Verify the tests pass.
- [ ] 6.3 Document usage (install the group, label, run tests, run the report or sweep) in a short section of `README.md` or `docs/`. Verify that the documented commands run as written.

## 7. Integration check

- [ ] 7.1 Run `uv run pytest -m clips` and `uv run python scripts/door_clip_report.py` on the real clips. Record the confusion matrix and timing errors in the change (no tuning in this change). Then run the full `uv run pytest` and `uv run ruff check . && uv run ruff format --check .` in `backend/`. Verify that both are green, and add a friction-log entry if PyAV or anything else hit friction.
