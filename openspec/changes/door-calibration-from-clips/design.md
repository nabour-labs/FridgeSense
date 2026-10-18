# Design

## Context

See proposal.md (Why) for the evidence. The relevant current state:

- The door check runs on decoded frames of the full event clip (2560×1440, including the camera's black privacy mask), every 500 ms (`clip_frames_checked` in `door_events.py`).
- Setup (`door_calibration.run`) measures four features per zone on the owner's references. It picks the largest margin, with ties going blue, color, change, brightness. The `change` feature compares against a 32×32 baseline made from the closed references.
- References and zone boxes are drawn on whatever picture the sheet got. Today that is the live view, falling back to the Ring still at 960×540. The live/still picture is framed differently from the recording: in a side-by-side of zone 1, the calendar magnet and door edges sit visibly lower and further right in clip frames.
- The closed anchor for alignment (`door-auto-calibration`) is the edge map of the newest closed reference. It inherits the same framing error.
- `_blue_lit` reuses `_colorful_mask` (chroma > 60, peak > 100), the mask the `color` feature also uses, and adds `B − max(R,G) > 20`.
- The PWA already has `camera/RecentClipPicker.tsx` (recent door-opening clips through `api.events(7)`, a scrubber, the frame grabbed in the browser and blurred by `POST /api/camera/frame`). The Reference images tab uses it. The stored `clip.mp4` is the uncropped recording cut to the open span, starting at the keyframe before the opening, so closed frames are available at its start.

Measurements behind the numbers, on stored S3 debug frames from 2026-10-17:

| Frame | `change` vs live-ref baseline | `change` vs closed clip frame | blue (old rule) | blue (strict rule) |
|---|---|---|---|---|
| evening, door closed | 0.094 | 0.016 | 0.000 | 0.000 |
| evening, door open | 0.126 | 0.099 | 0.060 | 0.038 |
| morning (daylight), door closed | — | — | 0.113 | 0.000 |

## Goals / Non-Goals

**Goals:**
- References, zone boxes and the closed anchor come from the same source and framing as the frames the door check scores.
- A miscalibrated setup degrades to the fridge-light rule instead of to "every motion is an opening".
- No new Ring calls, AWS resources or Bedrock calls.

**Non-Goals:**
- Making the `change` or `brightness` features robust to lighting or exposure. Instead, `blue` is preferred.
- Detecting openings of drawers that have no light. Those zones keep `change`/`brightness`, now with a baseline from clip frames.
- Server-side proof that a picture came from a clip. This is a single-owner demo, so the client's `source` is trusted.

## Decisions

### 1. Clip frames for setup, chosen in the browser (not a new backend frame route)
Reuse `RecentClipPicker` in the three Open/close detection sheets. It already lists recent openings, scrubs, grabs at most 960 px wide and blurs through `POST /api/camera/frame`. The grabbed frame has the clip's framing, and boxes are fractions, so 960×540 vs 2560×1440 does not matter.

*Alternatives:* (a) A backend route that picks a closed or open frame from a stored clip automatically. This needs more code and gives the owner less control over which moment is "open". (b) Rescaling or warping live frames to clip framing. The mapping is unknown and may change with Ring firmware. (c) Re-taking references from the live view. That is the current bug.

### 2. `source` on zones and references, with setup refusing `live`
A stored field is the smallest way to make old, mismatched data visible (the "Replace with a clip frame" note) and to stop setup from silently rebuilding bad rules from it. Missing field → `live`, so all existing data is flagged without a migration. `PATCH` with a new box and no `source` becomes `live`, because the client must state where the new picture came from.

*Alternative:* deleting existing references on deploy. That destroys data the owner can still look at, and needs a migration step.

### 3. Strict blue as separate constants, not a change to the color mask
Add `BLUE_MIN_CHROMA = 100`, `BLUE_MIN_PEAK = 120`, `BLUE_MIN_LEAD = 60` and a `_blue_mask` used only by `_blue_lit`. `color` keeps 60/100, so the stored `color` rules and their scenarios do not change. Setup, reference scores, self-tuning and the door check all call `measure(..., "blue")`, so one function change covers them all.

The thresholds come from a sweep over four rule strengths on the frames above. 40/80/100 still left 0.8% blue on daylit steel. 60/100/120 is the weakest rule that reads 0 on daylit steel. 80/120/150 also works but loses about a quarter of the open-interior signal. Task 1 re-checks the choice on labelled clips before any code changes. If a daylit opening drops below 0.01 at 60/100/120, adjust these constants and the spec values in this change.

### 4. Blue wins whenever it separates
`blue` is an absolute measure, so it needs no baseline and is unaffected by framing, exposure or people walking past in warm clothing. A `change` margin can be large for the wrong reason, as it was here, while `blue` still separated. The choice becomes: `blue` if it separates (margin ≥ 0.01), otherwise the largest margin among the rest. `self_tuning._zone_rule` shares the chooser (`_choose` plus the feature loop), so both pick the same way. Factor out one `choose_feature(values_by_feature)` that both call.

### 5. Suspect guard as a re-score, not a rejection
Bookend frames are almost always closed: Ring starts recording on approach and stops after the person leaves, and `door-auto-calibration` already relies on this. Two signals cover the observed failures: both bookends open (morning daylight with the old rule), and ≥ 90% open (the evening `change` rule). A minimum of 10 frames avoids flagging a 4 s clip of someone standing at an open fridge.

On a suspect clip the frames are already decoded and scored once. Re-scoring with `ZoneRule(box, "blue", "above", DOOR_THRESHOLD)` per setup zone costs about 40–240 small crops and no new downloads. Re-scoring lets a real opening inside a long clip still be recorded, where rejecting the event would lose it. It runs after alignment, so the boxes are the shifted ones.

*Alternative:* skipping analysis for suspect clips. That loses real openings, and the 2026-10-17 data shows the fridge light finds them well.

### 6. `suspect_streak` lives on the `ALIGN#{device}` item
That item is already read and written once per event for alignment, and is already per device. Add `suspect_streak` (number) next to `failures`. The setup run already calls `alignment.reset`, which also zeroes the streak. `setup_warnings` already reads this item for `camera_moved`, so the mismatch warning adds no table read. Streak write errors are logged and swallowed, like the other side effects of `_learn`.

### 7. Where the guard sits in `_fetch_stills`
After the frames are scored (and re-scored after alignment), and before `open_span`:
`values` → per-frame results → `suspect = is_suspect(results, source, len)` → if suspect, `values = fallback.zone_values(...)` and `rule_log["zones_source"] = "fallback"` → continue unchanged. `_learn` is skipped when `suspect`. The streak update goes right after the guard decision for clip-path events with setup rules. The run output gains `suspect: true` only when suspect.

## Risks / Trade-offs

- [Strict blue misses a dim or daylight-washed interior] → Task 1 checks on labelled clips and the 2026-10-17 morning frames. `DOOR_THRESHOLD` stays configurable. The constants are one place to change.
- [A zone where the fridge light is weak picks `blue` with a tiny margin] → The 0.01 minimum margin still applies, and a margin between 0.01 and the next feature's margin is accepted on purpose. The tab shows the margin so the owner can see it.
- [The owner has no recent clip with a closed or open moment] → While setup is broken, the guard's fallback produces real openings, each with a `clip.mp4`, and each clip starts closed. "No door openings with a clip in the last 7 days." is already handled.
- [A legitimately long opening (unloading groceries for 2 min) is flagged suspect] → It is re-scored with the fridge light, not dropped. It only counts toward the streak, and one normal event resets the streak.
- [Archive conflicts with `door-zones-defined` and `door-auto-calibration`] → This change only adds requirements to `door-calibration` and `setup-warnings`. Archive those two changes first.
- [Clip frames grabbed in the browser are re-encoded JPEGs at 960 px] → The features are fractions or 32×32 means, and are insensitive to this resolution.

## Migration Plan

1. Deploy backend and PWA together (`cdk deploy`, with Jayson's OK).
2. The banner shows `door_setup_missing`/`door_setup_mismatch` as appropriate. The Open/close tab marks all 3 zones and 9 references "Replace with a clip frame". Until replaced, the existing setup keeps running, and the suspect guard makes the fridge light decide.
3. The owner redraws the zones and adds open and closed references from recent clips, deletes the old ones, and runs setup.
4. Rollback: redeploy the previous version. The `source` and `suspect_streak` fields are ignored by old code.

## Test strategy

- **Unit (pytest, no I/O):** strict blue mask on synthetic pixels (daylit steel `(110,150,200)`, teal `(40,150,200)`, LED `(40,90,200)`, navy, warm food); `choose_feature` (blue preference, tiny blue margin, no blue, ties); `is_suspect` (all open, both ends, 92% open, normal, 8 frames, default rules); the fallback re-score picks the right span on a synthetic frame list.
- **Task-level (pytest + moto DynamoDB + stubbed S3/Ring/clip source, as in the existing `test_fetch_stills_clip.py`):** a suspect clip leads to `door_open` from the fallback with the right times and `zones_source = "fallback"`; a suspect walk-past leads to `not_door`; no `DOORSAMPLE` item for suspect events; streak increments, resets and survives write errors; setup run resets the streak.
- **API (pytest + moto, through `handlers/api.py` like `test_api_door_calibration.py`):** `source` accepted, defaulted, validated and listed; legacy items read as `live`; PATCH source rules; `run` refuses `live` zones and references; warnings include or exclude `door_setup_mismatch`, in last position, and survive read errors.
- **PWA (Vitest + Testing Library, `api` doubles like `RecentClipPicker.test.tsx`):** each sheet opens the clip picker and never calls live or snapshot; `source: "clip"` is sent; "Another frame"; cancel; mock video path; "Replace with a clip frame" notes and the disabled "Run setup" hint; mismatch banner link for the owner and none for a viewer.
- **Offline accuracy check (local only, no AWS/Bedrock):** `scripts/door_clip_report.py` over `tmp/*.mp4` with `tests/fixtures/clips/door_labels.json`, run with the strict blue default rule. Recall must not drop compared with today's report. The 2026-10-17 S3 debug frames (raw frames of morning and evening events, copied once into `tmp/`, never committed) go through the same check for the daylight case. The tests use synthetic fixtures. Real frames stay in `tmp/`.

## Open Questions

- Should the guard also run on the still-sampling fallback path (no clip)? That path is rare (clip unavailable) and has no bookends at 500 ms spacing. It is left out for now. This does not change the specs for the clip path.
