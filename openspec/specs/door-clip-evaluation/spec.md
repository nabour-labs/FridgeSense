# door-clip-evaluation Specification

## Purpose
Measures how well the door open/close check works on real fridge recordings kept on the developer's machine. It compares the check's verdict and open/close times with hand-written labels, both as integration tests and as a local accuracy report.

## Requirements

### Requirement: Clip labels fixture
The repository SHALL hold a labels file, `backend/tests/fixtures/clips/door_labels.json`, shaped as `{"clips": {"<file name>.mp4": {"openings": [{"opened_s": <number>, "closed_s": <number or null>}]}}}`. Times are seconds from the clip start. `closed_s = null` means the door was still open when the clip ended. An empty `openings` list means the door never opened. Loading SHALL reject a malformed file with an error naming the clip and the problem.

#### Scenario: Valid labels load
- **WHEN** the file labels `Ring_Fridge_20261015_1920.mp4` with `[{"opened_s": 4.0, "closed_s": 12.5}]` and `Ring_Fridge_20261015_1934.mp4` with `[]`
- **THEN** loading returns one opening for the first clip and none for the second

#### Scenario: Close before open
- **WHEN** a clip's opening has `opened_s = 10` and `closed_s = 8`
- **THEN** loading fails with an error naming that clip and saying `closed_s` must be after `opened_s`

#### Scenario: Overlapping openings
- **WHEN** a clip has openings `4–12` and `10–15`
- **THEN** loading fails with an error naming that clip and saying the openings overlap

#### Scenario: Negative or missing time
- **WHEN** an opening has `opened_s = -1` or no `opened_s` key
- **THEN** loading fails with an error naming that clip and `opened_s`

#### Scenario: Only one opening may stay open
- **WHEN** an opening with `closed_s = null` is followed by another opening in the same clip
- **THEN** loading fails with an error naming that clip and saying only the last opening may have `closed_s = null`

### Requirement: Clip videos stay local
Clip videos SHALL be read only from the local clips folder: `FRIDGESENSE_CLIPS_DIR` if set, otherwise the repository's `tmp/` folder. They SHALL NOT be committed, copied into the repository outside `tmp/`, or sent over the network. Frames written for labelling SHALL go only under `tmp/`.

#### Scenario: Clips folder from the environment
- **WHEN** `FRIDGESENSE_CLIPS_DIR=/data/fridge` is set and holds `Ring_Fridge_20261015_1920.mp4`
- **THEN** the clip tests and the report read that clip from `/data/fridge`

#### Scenario: Videos ignored by git
- **WHEN** a clip `tmp/Ring_Fridge_20261015_1920.mp4` exists
- **THEN** `git check-ignore tmp/Ring_Fridge_20261015_1920.mp4` reports it as ignored

### Requirement: Clip camera serves frames as stills
For a clip evaluation, the event window SHALL start at a fixed epoch time and end at that time plus the clip's duration. Each still-download request the pipeline makes at timestamp `t` SHALL be answered with the clip frame at `t − window start`, as a JPEG through the same redirect-and-download flow Ring uses. A timestamp outside the clip SHALL get HTTP 404.

#### Scenario: Frame at the requested time
- **WHEN** the window starts at `1786715596000` and the pipeline requests the still at `1786715603000`
- **THEN** the camera answers with the JPEG of the frame shown at 7.0 s into the clip, at the clip's full resolution

#### Scenario: Request past the end of the clip
- **WHEN** the clip lasts 20.0 s and a still is requested at window start + 25000 ms
- **THEN** the download answers 404 and that still is recorded as missing, with no error raised

#### Scenario: Unreadable clip
- **WHEN** a labelled clip exists but is not a decodable video
- **THEN** that clip's test fails with an error naming the clip file, and the other clips still run

### Requirement: Per-clip door check test
For each labelled clip found in the clips folder, a test marked `clips` SHALL run the unchanged fetch-stills task on that clip with the configured door check (`DOOR_ZONES`, `DOOR_THRESHOLD`, `STILL_INTERVAL_MS`, or their defaults). It SHALL check the outcome and the event's open and close times against the labels. The tolerance is 1.5 × the still spacing: the still interval, or the wider spacing the pipeline uses when a long window hits its 30-still cap. With several openings in one clip, the expected span runs from the first `opened_s` to the last `closed_s`. A `null` close means the window end.

#### Scenario: Opening found with correct times
- **WHEN** a clip is labelled `[{"opened_s": 4.0, "closed_s": 12.5}]`, the still interval is 1000 ms, and the door event's `opened_at` is window start + 4.6 s and `closed_at` is window start + 13.0 s
- **THEN** the test passes

#### Scenario: Open time too far off
- **WHEN** the same clip's door event has `opened_at` = window start + 6.0 s
- **THEN** the test fails, and the message names the clip, the labelled and detected open times, and the 1.5 s tolerance

#### Scenario: Missed opening
- **WHEN** a clip is labelled with one opening and the task ends with `not_door`
- **THEN** the test fails with a message naming the clip and "missed opening", along with the best zone value and the threshold

#### Scenario: False opening
- **WHEN** a clip is labelled `[]` and the task ends with `door_open`
- **THEN** the test fails with a message naming the clip and "false opening", along with the detected open and close times

#### Scenario: No opening, none detected
- **WHEN** a clip is labelled `[]` and the task ends with `not_door`
- **THEN** the test passes

#### Scenario: Door still open at clip end
- **WHEN** a clip is labelled `[{"opened_s": 3.0, "closed_s": null}]` and the door event's `closed_at` is the window end
- **THEN** the close time counts as correct

#### Scenario: Two openings in one clip
- **WHEN** a clip is labelled `[{"opened_s": 2.0, "closed_s": 6.0}, {"opened_s": 15.0, "closed_s": 20.0}]`
- **THEN** the expected open time is window start + 2.0 s and the expected close time is window start + 20.0 s

#### Scenario: Shorter still interval
- **WHEN** `STILL_INTERVAL_MS=500` is set
- **THEN** stills are requested about every 500 ms and the tolerance is 0.75 s

#### Scenario: Long clip hits the still cap
- **WHEN** a clip lasts 120.0 s and the still interval is 1000 ms
- **THEN** 30 stills are requested about 3.9 s apart and the tolerance is 1.5 × that spacing (about 5.8 s)

### Requirement: Clip tests skip when they cannot run
The clip tests SHALL be skipped, not failed, when they cannot run: the clips folder is missing, a labelled clip is not in it, or the video decoder is not installed. Each skip reason SHALL say which. A clip in the folder without a label SHALL be neither tested nor failed. The default test run SHALL keep working and passing without the clips or the decoder.

#### Scenario: Fresh checkout or CI
- **WHEN** `uv run pytest` runs with no `tmp/` clips and without the `clips` dependency group
- **THEN** every clip test is reported as skipped, and the run's result is unaffected

#### Scenario: One labelled clip missing
- **WHEN** `door_labels.json` labels `Ring_Fridge_20261015_2025.mp4` and that file is not in the clips folder
- **THEN** that clip's test is skipped with a reason naming the file, and the other clips run

#### Scenario: Decoder not installed
- **WHEN** the clips are present but the video decoder package cannot be imported
- **THEN** every clip test is skipped with a reason saying to run `uv sync --group clips`

#### Scenario: Run only the clip tests
- **WHEN** the developer runs `uv run pytest -m clips`
- **THEN** only the clip tests run

### Requirement: No live services in clip runs
Clip tests and the report SHALL NOT call Ring, AWS or Bedrock. Storage SHALL use moto, and face blurring SHALL use the test fake that reports no faces.

#### Scenario: Network blocked
- **WHEN** the clip tests or the report run with every outbound request not handled by the fake camera set to fail
- **THEN** they complete without any request reaching the network

### Requirement: Accuracy report
A local command, `uv run python scripts/door_clip_report.py`, SHALL run every labelled clip that is present and print one row per clip. Each row shows the labelled and detected verdict, open and close errors in seconds, and the best zone value. The output SHALL end with a confusion-matrix summary (true and false openings, missed openings, true non-openings) and the mean and maximum absolute open and close errors over correctly detected openings. The command SHALL exit 0 whatever the accuracy.

#### Scenario: Report over all clips
- **WHEN** three labelled clips are present: one opening detected 0.4 s early, one opening missed, and one no-opening clip correctly rejected
- **THEN** the summary reads `TP 1  FP 0  FN 1  TN 1`, and the open-error line shows mean and max of 0.4 s

#### Scenario: No clips present
- **WHEN** no labelled clip is in the clips folder
- **THEN** the command prints `no labelled clips found in <folder>` and exits 0

#### Scenario: Unlabelled clips listed
- **WHEN** `tmp/` holds a clip with no entry in `door_labels.json`
- **THEN** the report lists it under `unlabelled` and does not score it

### Requirement: Threshold and interval sweep
The report SHALL accept `--threshold` and `--interval` lists, given as comma-separated values. It SHALL run every combination and print one summary row per combination: threshold, interval, TP, FP, FN, TN, and mean open and close error. Bad values SHALL stop the command with a non-zero exit before any clip is decoded.

#### Scenario: Sweep two thresholds and two intervals
- **WHEN** the developer runs the report with `--threshold 0.01,0.03 --interval 500,1000`
- **THEN** four summary rows are printed, one per combination

#### Scenario: Bad sweep value
- **WHEN** the report runs with `--interval 0` or `--threshold abc`
- **THEN** it exits non-zero with an error naming the option, before any clip is decoded

### Requirement: Stills dump for labelling
With `--dump`, the report SHALL write each sampled still for each clip as `<dump dir>/<clip name>/<offset in ms>.jpg`. The dump dir is `--dump-dir`, default `tmp/clip-stills`. It SHALL also write a `values.csv` per clip with offset, zone values and per-still verdict. This helps the developer pick opened and closed times. Paths outside `tmp/` SHALL be refused.

#### Scenario: Dump stills
- **WHEN** the report runs with `--dump` on a 20 s clip at a 1000 ms interval
- **THEN** `tmp/clip-stills/Ring_Fridge_20261015_1920/` holds one JPEG per sampled still, named by offset, plus `values.csv` with one row per still

#### Scenario: Dump outside tmp refused
- **WHEN** the report runs with `--dump-dir backend/tests/fixtures`
- **THEN** it exits non-zero with an error saying stills may only be written under `tmp/`, and writes nothing
