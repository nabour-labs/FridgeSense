# Design

## Context

See proposal.md (Why) for the accuracy problem. The current state that shapes the approach:

- `fetch_stills` (clip path) decodes the event clip at `DOOR_FRAME_INTERVAL_MS` (500 ms) and keeps every frame as a full-size JPEG in `raw`. The door check finds the open span, `pick()` takes 4 evenly spaced frames, and those are cropped to `STILL_CROP`, blurred and stored as `still-<n>.jpg`. `store_open_clip` remuxes the open span into `clip.mp4` (or `clip-raw.mp4` while blurring is on). The `BlurClip` step blurs it only **after** `Analyze` and `Save`, and takes up to ~3.5 min.
- `analyze_task` reads the stored stills from S3 and calls `NovaAnalyzer.analyze`. `build_request` sends at most 4 JPEGs plus the instruction text. The `record_fridge_changes` answer is `{added, removed}`, and `save_task` applies confidence ≥ 0.7 and stores `proof`.
- Each device's fridge area (`FRIDGEAREA#<device>`, drawn by the owner) is stored but used only by setup warnings. Today's box is `0.362, 0.329, 0.233, 0.611`.
- Nova 2 Lite video: one video per request, inline bytes up to 25 MB. Videos up to 16 min are sampled at **1 frame per second**, and every frame is resized (with distortion) to **672×672**, about 288 tokens per frame ([Nova 2 multimodal guide](https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-multimodal-models.html)).
- The in-progress change `face-blur-setting` also edits the "Only blurred stills are analyzed" requirement.

## Goals / Non-Goals

**Goals:**
- Nova sees every 500 ms frame of a normal opening, at the highest detail its 672×672 budget allows, with a prompt that asks about hands, not shelves.
- Direction is decided in code from explicit evidence. A wrong guess is dropped rather than applied.
- The before/after improvement is measurable from fixtures, without live calls in tests.

**Non-Goals:**
- Choosing frames by motion, or tracking items between openings.
- Proof frames cut from the video. Proof stays on the 4 stored, blurred stills.
- Changing the confidence cutoff or the pending-change flow.

## Decisions

### D1. Evidence fields, direction in code
The tool returns `{observations, items[{item, category, quantity, confidence, going_in, coming_out, moments}]}`. `parse_response` derives `FridgeChanges(added, removed)` from the flags and returns the dropped items separately for logging, so `save_task` and the inventory code stay unchanged.
- *Why over keeping `added`/`removed` + an evidence field:* when Nova labels the direction itself, it keeps the habit of filling both lists from what it sees on the shelves. Two booleans per item are easier to answer honestly, and the code can reject contradictions.
- `observations` comes first in the schema so Nova writes a time-ordered account before it lists items. This costs ~100 output tokens (~$0.0003).
- *Alternative rejected:* a second "verify" call per opening. It doubles cost and latency, and the eval can show whether it is needed later.

### D2. Prompt
The prompt says to watch hands crossing the fridge opening. Held going in and not coming out means `going_in`. The reverse means `coming_out`. Items on shelves, in the door bins or in drawers that nobody carries are not changes. When unsure, set both to false. The inventory list is renamed "Names already in the inventory (reuse them for the same kind of item; do not report them unless you see them carried)", and "Compare them" is gone. The exact strings live in `analysis.py` constants that the tests import.

### D3. Analysis video built in `fetch_stills`, not from `clip.mp4`
The frames are already decoded and in memory (`raw`), so the video is encoded from them. The frame before the open span plus the open span (thinned to ≤ 40 frames by a uniform step) are each cropped to the analysis box. They are encoded with PyAV `libx264` (`yuv420p`, even dimensions, CRF ~23) at **1 fps playback**, so Nova's 1 fps sampling sees each 500 ms frame exactly once (2× slow motion).
- *Why not send `clip.mp4`:* it is the full 2560×1440 frame, and at 1 fps sampling Nova would see only every other 500 ms moment. While blurring is on it is also `clip-raw.mp4` and must stay unlinked. Re-encoding a crop keeps the video small (~0.3–1 MB) and matched to Nova's sampling.
- *Why ≤ 40 frames:* ~11.5k tokens ≈ $0.004 per opening at the configured input price. The 115 s outlier gets 3 s spacing, which is still 10× denser than today's ~38 s.
- `libx264` is confirmed in the PyAV 19 wheel locally. The Lambda arm64 image is checked in a task.
- Mapping back: video second `s` corresponds to real time `start_ms + s · frame_ms`. Each moment maps to the nearest `still_ms` for proof.

### D4. Storage and lifetime of `analysis.mp4`
It is stored under the event prefix with tag `transient=true`, so the existing 1-day lifecycle rule (`door-pipeline.ts`, the raw-clip rule) catches runs that die. `analyze_task` deletes it in a `finally` block, but only when the step is finishing: valid answer, invalid twice, or rejected. On `BedrockRetryable` it leaves the video so Step Functions' retry can use it. The analyze Lambda gets `s3:GetObject` and `s3:DeleteObject` on `*/analysis.mp4`. The fetch Lambda already has `PutObject` on the bucket, which is checked in a task. A duplicate or not-door outcome never uploads it: the video is encoded only after the door event claim succeeds, or deleted on the duplicate branch, matching how `clip-raw.mp4` is handled.

### D5. Analysis crop box
`analysis_box(area) = area` widened by 10% of its width on each side and by 5% of its height above and below, clamped to [0, 1]. The pipeline loads the fridge area once per motion, as it does for the face-blur setting, and uses the box for both the stored stills and the video. Without an area it falls back to `STILL_CROP`.
- For today's box, a 716×968 crop replaces 870×1440, so the fridge fills ~1.9× more of Nova's 672×672 input (the aspect ratio goes from 0.60 to 0.74, which also means less vertical squash).
- *Alternative rejected:* padding to a square. It adds pixels that hold nothing, and the distortion at 0.74 is mild.

### D6. Face-blur scope
The owner decided (2026-10-18) that Nova input need not be blurred, but anything the front end shows must be. Stored stills, `clip.mp4` and proof stay blurred: a proof is only ever an index into the stored, blurred stills, never a frame of the analysis video. A later change that cuts proof frames from the video moment must run them through the face blurrer before storing them. The trace records the video block with no `key`, so `GET /api/debug/motions/{id}` (which turns every `key` into a URL) can never link it.

### D7. Eval
- **Labels:** the 12 openings with window start between 2026-10-18T21:32Z and 2026-10-19T00:01Z. Each opening's `clip.mp4` (blurred, cut to the open span) is downloaded to `tmp/analysis-eval/<start_ms>.mp4` before the 7-day expiry (~Oct 25). Claude drafts labels from the frames, and Jayson confirms or corrects every one before the fixture is committed. Only item names and quantities go in the repo.
- **Baseline:** the tool input from each opening's stored `nova-*-1.json` trace (the last `ok` attempt), copied to `fixtures/analysis_eval/baseline/`.
- **Scoring** lives in the test harness package (`backend/tests/analysis_eval/`), next to `tests/clips/`, and reuses `analysis.parse_response` and `inventory.normalize_name` so it scores what the pipeline would apply.
- **Live run:** `scripts/analysis_eval.py --live <run>` builds the analysis video from each local clip with the production encoder and crop, calls Nova (≈ 12 × $0.005), and writes `fixtures/analysis_eval/<run>/`. It runs only with Jayson's OK, since it costs money. The local clips are already blurred, which matches the production input closely enough for this purpose.
- **Target** (a goal, not a test assertion): direction errors 0, and precision at least double the baseline's, without recall dropping below the baseline's.

### D7 results

Labels: Jayson approved the drafts on 2026-10-18 ("ok go ahead"). 6 openings are judged and 6 are skipped because the item or direction can't be told from the clip. 4 of the 6 judged openings moved nothing (3 water-dispenser visits and 1 false motion); the other 2 removed a soda can and 2 eggs.

| Run | TP | FP | FN | Direction errors | Precision | Recall |
|---|---|---|---|---|---|---|
| baseline (4 stills, old prompt) | 0 | 10 | 2 | 1 | 0.0 | 0.0 |

## Test strategy

- **Unit (pytest, no network):**
  - `build_request` for the stills, video, references+video and cache+video cases. Prompt strings. Schema order and required fields.
  - `parse_response`: evidence flags, drops with reasons, the old shape being invalid, moments to proof for stills and video.
  - `analysis_box` math and clamping.
  - Thinning of frame indexes.
  - Mapping still times to `still_ms`.
- **Contract (botocore Stubber / moto):**
  - Converse stubbed with canned responses in `tests/fixtures/nova/` (new: `converse_items.json`, `converse_items_dropped.json`, `converse_old_shape.json`).
  - S3 via moto: `analysis.mp4` stored with tag `transient=true`, read by `analyze_task`, deleted after the step (or kept on a retryable error), missing object → stills fallback.
  - Trace JSON has the video entry with no `key`.
- **Integration (moto + fake Ring):** `fetch_stills` on a small synthetic clip (built with PyAV in a fixture, like `tests/clip_video.py`) produces `analysis_video` with the expected frame count and size, plus `still_ms`. Also covered: the encode-failure, upload-failure and fallback paths, and no `analysis.mp4` on not-door or duplicate outcomes.
- **Eval:** label-loading and scoring unit tests. A test that scores `baseline/` for all 12 labelled openings and checks that the report runs and totals match the per-opening sums. A network-blocked test of the report command.
- **Stubbed:** Bedrock (Stubber), S3/DynamoDB (moto), Ring (fake client), Rekognition (fake blurrer). The analysis tests use no real fridge video. The eval clips stay in `tmp/` and are used only by the opt-in live script.

## Risks / Trade-offs

- [Nova still reports shelf items with `going_in = true`] → The eval measures it. The prompt says to choose false when unsure. Dropped items are logged with reasons, so tuning is data-driven.
- [The hand evidence drops real changes (lower recall)] → The eval tracks recall. Dropped items stay visible in logs and traces. If recall falls too far, a later change can save `no_hand_evidence` items as pending instead of dropping them.
- [Unblurred frames reach Bedrock] → The owner accepted this. The video is transient and unlinked, deleted after analysis, and expires within 1 day otherwise. Bedrock does not store prompts.
- [`libx264` missing or slow in the Lambda image] → A task checks the deployed image's PyAV codecs. The fallback is the `mpeg4` encoder (also in the wheel). 40 frames at ~716×968 encode in well under 1 s.
- [The fetch Lambda runs out of memory while encoding] → Frames are already in memory as JPEGs. Encoding streams one frame at a time.
- [Labels are guesses] → Every label is confirmed by Jayson. Openings he can't judge are labelled with a `note` and left out of the totals.
- [Conflicts with the `face-blur-setting` delta] → Archive `face-blur-setting` first, then re-check this change's RENAMED/MODIFIED block against the new main spec before archiving it.

## Migration Plan

1. Merge to `local` after the full suite passes. Deploy with `cdk deploy` (Jayson's OK). The new IAM grants and the code ship together, with no data migration.
2. Old door events keep their `{added, removed}`-derived changes. Only new openings use the new schema.
3. Rollback: redeploy the previous build. Leftover `analysis.mp4` objects expire within 1 day through the transient tag.
