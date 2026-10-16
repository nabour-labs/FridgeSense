# Design

## Context

- The door check measures one *feature* per zone (`measure` in `backend/src/fridgesense/door_events.py`). The features are `color`, `change` and `brightness`. `FEATURES` lists them, and its order is also setup's tie order. Without a setup result, every zone gets a `color` rule at `DOOR_THRESHOLD` (default 0.02).
- The CDK stack always sets `DOOR_THRESHOLD`, from the `doorThreshold` context, default `"0.02"` (`infra/lib/fridgesense-stack.ts`). Changing only the backend default would not reach the deployed Lambdas.
- Setup (`door_calibration.run`) tries every name in `FEATURES` for each zone, so a new feature added there is picked up by setup without other code changes.
- Measurement on the 344 stills dumped from the 12 local clips, scored against the draft labels from `door-detection-clip-tests`:

  | Rule | Open stills found | False opens | Missed opens |
  |---|---|---|---|
  | `color` ≥ 0.02 (today) | 66 | 4 | 6 |
  | `color` ≥ 0.01 | 70 | 8 | 2 |
  | `blue` ≥ 0.01 | 69 | 0 | 3 |
  | `blue` ≥ 0.02 | 64 | 0 | 8 |

  The 4 false opens today are a snack, a plate (twice) and a red packet in someone's hand, all with no blue-lit pixels. Two of the 3 remaining misses with `blue` are label edges: a door still swinging shut, and a door ajar with the light not yet on.

## Goals / Non-Goals

**Goals:**
- No false door opening from warm-coloured food or clothing in front of the closed fridge.
- Catch at least as many open stills as today on the local clips.
- Keep stored setup results that use `color` working unchanged.

**Non-Goals:**
- Splitting merged openings, changing still spacing or the 30-still cap, or adding zones.
- Learning the interior colour per device. A fixed blue rule is enough for this fridge.

## Decisions

1. **`blue` is a new feature, not a change to `color`.** `blue` = the share of pixels with `max − min > 60`, `max > 100` and `B − max(R, G) > 20`. That is the existing `color` mask AND a blue-dominance mask. Keeping `color` as it is means stored setup results, their thresholds, and the setup scenarios built on `color` keep their meaning. *Alternative:* redefine `color` as blue-only. That is simpler, but it would silently change what an existing setup's thresholds mean.

2. **Default threshold 0.01, set in both places.** `DEFAULT_THRESHOLD` becomes 0.01, and so does the CDK `doorThreshold` context default. It stays overridable with `-c doorThreshold=…`. 0.01 is the best row in the table: 0.02 drops 5 true open stills and adds no protection against false opens.

3. **The margin `> 20` on blue dominance.** The lit interior measured `B − max(R,G)` far above 20. Grey steel is near 0 and is already excluded by the chroma rule. 20 leaves room for JPEG noise without letting purple or teal clothing through easily. This is a constant, like `MIN_CHROMA`, not a setting.

4. **Setup tie order: blue, color, change, brightness.** For a lit-fridge open reference, `blue` and `color` usually separate with the same margin. Preferring `blue` keeps the food protection on set-up devices. When the open reference is not blue (for example a drawer with no light), `blue` does not separate and setup falls back to `color` as before.

5. **Measure before and after with the clip harness.** Run `door_clip_report.py` and `pytest -m clips` before the change and after it, with the labels as confirmed by Jayson, and record both in this change. This is the check that the gain holds on confirmed labels and not only on the draft.

## Risks / Trade-offs

- [All 12 clips are from one evening, under kitchen lights] → Daylight is unlikely to change the interior LED colour, but a blue shirt or a blue packet in front of the doors could now cause a false open. Note it in the report. If it shows up, raise the margin or add a minimum blue level.
- [Measured on draft labels] → Decision 5 repeats the measurement on confirmed labels before archiving.
- [Default zones and the new rule were both tuned on these same clips] → Expect optimistic numbers. Hold out new clips as they come.
- [This change modifies requirements in two unarchived changes (`door-zone-setup`, `pipeline-debug-traces`)] → Archive those first, then this one, so the MODIFIED deltas apply to the right text.
- [A device with a stored `color` setup keeps the old behaviour] → Re-running setup picks `blue`. That is a manual step and is out of scope here.

## Test strategy

- **Unit (backend, pytest):** `measure(..., "blue")` on synthetic JPEGs from `color_jpeg`: a blue `(40,90,200)` block, a yellow `(220,170,40)` plate, a red `(200,40,40)` packet, navy `(20,25,60)`, and plain greys. The door-check scenarios: Food in front of closed doors, Faint fridge light at the 0.01 default, Drawer seen only in the drawers zone (now blue), Box from config, Threshold inclusive, and Stored color setup still works. The setup scenarios: Blue preferred on a tie, and Color chosen when the open reference is not blue. Existing tests that assume `color` at 0.02 as the default are updated to match the modified scenarios, never weakened.
- **Contract:** `GET /api/door-calibration` `defaults` and the debug trace `rule` show `feature = "blue"` with threshold 0.01 (`test_api_door_calibration.py`, `test_door_traces.py`).
- **PWA (Vitest):** "Blue light feature named" on the Open/close detection tab, with the fake API.
- **Infra (Jest/Vitest):** stack and pipeline tests expect `DOOR_THRESHOLD = "0.01"`.
- **Integration (local only, `-m clips`):** the per-clip tests and the report on the 12 clips, before and after. Stubbed as in `door-detection-clip-tests`: Ring through the clip camera, S3 and DynamoDB through moto, and faces through `FakeBlurrer`. No live Ring, AWS or Bedrock.
