# Tasks

## 1. Eval data (do first: the clips expire around Oct 25)

- [ ] 1.1 Download `clip.mp4` for the 12 openings from 2026-10-18T21:32Z to 2026-10-19T00:01Z to `tmp/analysis-eval/<start_ms>.mp4`, and check that `git check-ignore tmp/analysis-eval/*.mp4` lists all 12 (S3 read only; covers "Eval clips ignored by git")
- [ ] 1.2 Copy each opening's last `ok` Nova tool input from its `debug/nova-*.json` trace to `backend/tests/fixtures/analysis_eval/baseline/<start_ms>.json`, holding only the tool input, and check that 12 files exist
- [ ] 1.3 Draft `labels.json` from frames dumped to `tmp/analysis-eval/frames/`, then have Jayson confirm or correct every opening; verify the file has 12 openings and Jayson's OK is recorded in the commit message

## 2. Eval scorer and report

- [ ] 2.1 Write failing tests for label loading: "Valid labels load", "Nothing moved", "Bad quantity"
- [ ] 2.2 Implement the label loader in `backend/tests/analysis_eval/` and verify 2.1 passes
- [ ] 2.3 Write failing tests for scoring: "Perfect opening", "Inventory echo", "Direction flipped", "Alias matches", "Totals", "Nothing predicted and nothing labelled", "Baseline answers in the old shape", "Missing answer"
- [ ] 2.4 Implement the scorer, reusing `inventory.normalize_name` and reading old-shape answers, and verify 2.3 passes
- [ ] 2.5 Write failing tests for the report command: "Compare baseline with a new run" (using a second fixture run), "Offline by default" (network blocked), and a test that the totals of `baseline/` against `labels.json` equal the per-opening sums
- [ ] 2.6 Implement `backend/scripts/analysis_eval.py --run` and verify 2.5 passes; record the baseline totals in the change's design.md under D7

## 3. Hand-evidence prompt and schema

- [ ] 3.1 Write failing tests for "Schema order and required fields", "Hand-evidence instructions", "Schema and prompt ask for images", and an updated "Request built from stills and inventory" / "Empty inventory" / "Stills sent as bytes"
- [ ] 3.2 Rewrite `TOOL_SPEC` and `INSTRUCTIONS` in `analysis.py` and verify 3.1 passes, with the existing owner's-config and cache-point tests still green
- [ ] 3.3 Write failing tests for parsing: "Valid answer", "Text before the tool call", "Values out of range", "Evidence flags that are not booleans", "Old answer shape", "Invalid answer retried once", "Invalid answer twice" (new canned responses `converse_items.json`, `converse_items_dropped.json`, `converse_old_shape.json`)
- [ ] 3.4 Write failing tests for direction: "Seen going in", "Seen coming out", "Item only seen on a shelf", "Taken out and put back", "Every item dropped", "Low confidence with evidence"
- [ ] 3.5 Implement evidence parsing, deriving `FridgeChanges` and returning dropped items with `change_dropped` logs, and verify 3.3–3.4 pass
- [ ] 3.6 Write failing tests for "Proof kept", "Out-of-range, duplicate and extra numbers", "Non-integer numbers", "Images missing or malformed", and "Observations not stored on the event"; implement moments → proof for stills and verify they pass
- [ ] 3.7 Update existing tests that built `{added, removed}` answers (analyze task, save task, traces, fixtures) to the new shape without weakening any assertion, and verify `uv run pytest` is green

## 4. Analysis crop

- [ ] 4.1 Write failing tests for "Box from the fridge area", "Box clamped at the frame edge", "No fridge area"
- [ ] 4.2 Implement `analysis_box` and verify 4.1 passes
- [ ] 4.3 Write failing tests for "Fridge area wins over STILL_CROP", plus the existing crop scenarios ("Crop to the visible strip", "Analysis sees the cropped still", "No crop configured", "Door check ignores the crop", "Invalid crop config") with a device that has no fridge area
- [ ] 4.4 Load the fridge area once per motion in `fetch_stills` / `handlers/pipeline.py`, crop stills to the analysis box, and verify 4.3 passes

## 5. Analysis video in fetch-stills

- [ ] 5.1 Write failing tests for frame selection and thinning: "Long opening thinned", "Span starts at the first frame"
- [ ] 5.2 Implement frame selection and verify 5.1 passes
- [ ] 5.3 Write a failing integration test for "Short opening" using a synthetic PyAV clip and moto S3 (frame count, size ±2 px, 1 fps, `transient=true` tag, `analysis_video` output)
- [ ] 5.4 Implement the encoder (`libx264`, `yuv420p`, even dimensions, 1 fps) in `clip_frames.py` and the upload in `door_events.py`, and verify 5.3 passes
- [ ] 5.5 Write failing tests for "Encoding or upload fails", "No video on the fallback path", "Not a door opening" (not_door and duplicate), and "Built while face blurring is on"; implement and verify they pass
- [ ] 5.6 Write failing tests for "Times match the stored stills" and "Still dropped by face detection"; add `still_ms` to the step output and verify they pass

## 6. Video in the analysis request

- [ ] 6.1 Write failing tests for "Video instead of stills", "References before the video", "Cache point after the video"
- [ ] 6.2 Extend `build_request` with an optional video and verify 6.1 passes
- [ ] 6.3 Write failing tests for "Video object missing", "Analysis video deleted after analysis" (valid, invalid twice, rejected), and "Analysis video deleted when the step is retried" (kept on `BedrockRetryable`)
- [ ] 6.4 Make `analyze_task` read `analysis_video`, fall back to stills, and delete the video in its finishing paths; verify 6.3 passes
- [ ] 6.5 Write failing tests for "Proof mapped from video seconds", "Video moments past the end" and "Proof shown blurred" (moto S3, fake blurrer, `GET /api/events` proof link); implement the mapping through `analysis_video` and `still_ms`, and verify they pass
- [ ] 6.6 Write failing tests for "Analysis receives blurred bytes", "Analysis video never shown" (door event fields, `GET /api/events`, `GET /api/debug/motions/{id}`), "Door check runs on downloaded stills" and "No debug stills when tracing is off"; verify they pass (implement any gaps)

## 7. Traces

- [ ] 7.1 Write failing tests for "Video traced without a key" and "Response kept" (with observations), and update "Request with references" / "Image keys are retrievable" / "Owner's instructions shown" to the new prompt
- [ ] 7.2 Record the video block in `traces.py` with `frames`, `frame_ms` and `bytes` and no key, and verify 7.1 passes

## 8. Infra

- [ ] 8.1 Write a failing CDK assertion test that the analyze Lambda's role has `s3:GetObject` and `s3:DeleteObject` on `*/analysis.mp4` and the fetch Lambda can put objects with tags; add the grants and verify `npm test` in `infra/` passes
- [ ] 8.2 Check that the Lambda image's PyAV has `libx264`: run `cdk synth`, build the bundled asset locally, run `python -c "import av; av.codec.Codec('libx264','w')"` in it, and record the result (add a friction-log entry if it is missing and switch to `mpeg4`)

## 9. Measure and wrap up

- [ ] 9.1 With Jayson's OK (it calls Bedrock, ≈ $0.06), run `scripts/analysis_eval.py --live video-v1` over the 12 local clips, commit `fixtures/analysis_eval/video-v1/`, and paste the baseline vs video-v1 tables into the change's design.md D7
- [ ] 9.2 If the D7 target is missed, write up the dropped and false-positive items from the run as open questions for Jayson before changing the prompt (no silent prompt tweaks after measuring)
- [ ] 9.3 Update README's analysis section (video input, hand evidence, crop, face-blur scope) and add friction-log entries for any Bedrock video or PyAV friction actually hit; verify the README commands run as written
- [ ] 9.4 Run the full suite and linters green: `uv run pytest` and `uv run ruff check . && uv run ruff format --check .` in `backend/`, `npm test` in `infra/` and `pwa/`; report the commands and results
