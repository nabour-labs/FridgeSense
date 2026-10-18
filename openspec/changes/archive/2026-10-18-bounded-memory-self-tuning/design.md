# Design

## Context

See proposal.md (Why). `door_events._learn` passes `self_tuning.learn` the event's frames as JPEG bytes: up to about 240 clip frames at 500 ms, or sampled Ring stills. `sample_event` runs `_open_rgb` on every frame up front, then makes one loop over the images for each rule. With 2K frames, the list alone is over 2 GB. `_open_rgb` returns its input unchanged when given a PIL image, which some tests rely on.

The `door-self-calibration` capability is not in `openspec/specs/` yet, because `door-auto-calibration` has not been archived. This change ADDs a single requirement to it. Archiving this change first creates the main spec with that requirement, and `door-auto-calibration` ADDs its own requirements later. The names don't overlap.

## Goals / Non-Goals

**Goals:** at most 2 decoded frames alive while an event is sampled, and the same `ZoneSample`s as today.

**Non-Goals:** speeding sampling up, and changing `learn`'s signature or the other self-tuning code.

## Decisions

1. **Score in a single pass over the frames, then re-decode the winners.** Decode the bookend once and build each rule's closed `Look` from it. Rules that call the bookend open get `(None, None)`, as before. Then decode each non-bookend frame in turn. For every active rule, compute `_change` against that rule's closed thumbnail and keep `(best_index, best_change)`, using the same `>=` comparison and threshold, so ties still go to the later frame. Drop the frame before decoding the next one. Finally, for each rule with a best index, decode that frame again and build its open `Look`.
   - *Alternative: one pass per rule, decoding lazily each time.* It also bounds memory, but it decodes N×rules frames instead of N plus at most one per rule.
   - *Alternative: raise the Lambda to 3–4 GB.* It costs more on every invocation and still fails on a longer clip.
2. **Measure memory by counting live decoded images in the test.** Wrap `self_tuning._open_rgb` with a spy that registers each returned image with `weakref.finalize` and tracks the highest number alive at once. CPython frees each frame when the loop variable is rebound, so the count is deterministic. The current code holds all N, so the test fails for the right reason.

## Risks / Trade-offs

- [The best frame is decoded twice, up to one extra decode per zone] → a JPEG decode takes milliseconds, compared with the 20–25 s the step spends decoding the clip.
- [Callers that pass PIL images keep them all alive themselves] → that isn't this function's allocation, so the spy counts only the images `_open_rgb` returns. Production passes bytes.

## Migration Plan

Deploying needs no migration. Deploy with `cdk deploy`, with Jayson's OK. To roll back, redeploy the previous commit.

## Test strategy

- Unit (pytest, moto `aws` fixture as in `test_self_tuning.py`):
  - *Long event sampled with two frames decoded*: 240 synthetic `color_jpeg` frames with one lit frame. Assert the sample is stored and the spy's peak is ≤ 2.
  - *Several zones share one pass*: a two-rule check over 40 frames, with a left block at frame 10 and a right block at frame 30. Assert each zone's open `blue` matches its own frame, and peak ≤ 2.
  - The existing sampling tests (opening sampled, missed opening, no clear opening, bookend not closed, first bookend, shifted zone) must stay green. They guard that results are unchanged.
- Fixtures: none beyond `color_jpeg`. Nothing live: DynamoDB runs on moto.
