# Proposal

## Why

One Ring motion window can hold more than one door opening. The door check's open span runs from the first open frame to the last open frame, so two openings with a closed gap between them merge into one door event. The real case is window 1792366696502 (2026-10-18T23:38:16Z): open from 0–38 s, closed from 38–111 s, then a different person opened it at 111 s. That was recorded as one 115 s event, and Nova got one long analysis covering both people. Duration stats are wrong, and each analysis has to cover more than one opening's worth of changes.

## What Changes

- A run of closed frames (or stills) lasting **10 s or more** ends an opening. Shorter closed runs, such as someone blocking the zone for a moment, stay inside the opening.
- Each opening in a motion becomes **its own door event**, with its own `opened_at`, `closed_at`, `duration_s`, stills, `still_ms`, open-span clip (`clip.mp4` / `clip-raw.mp4`), analysis video (`analysis.mp4`) and Nova analysis. Each is built only from its own span.
- The first opening keeps today's keys (`DOOR#<iso window start>#<device_id>`, stills prefix `events/<start_ms>/`). Opening *k* ≥ 2 gets `DOOR#<iso window start>#<device_id>#<k>` and the prefix `events/<start_ms>/opening-<k>/`, so its media never overwrites another opening's.
- All door events of a motion are written in the same transaction as the motion's one Ring-event claim, so a re-run still creates no duplicates.
- The fetch-stills output gains `openings`: one entry per door opening that goes on to analysis. Its top-level fields keep describing the first opening, as today.
- The workflow runs Analyze → Save → clip blur once per entry in `openings`, one at a time and in order. A failed opening is marked `analysis_failed`, the remaining openings still run, and the run then ends in `AnalysisFailed`.
- The door trace (`door.json`) lists every opening. The trace endpoint also resolves a later opening's door event id to the motion's trace.
- The door-clip evaluation compares the first detected opening with the labelled openings before the first gap of 10 s or more.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `door-event-detection`: an open span ends at a closed run of 10 s or more, each opening in a motion becomes its own door event with its own media and keys, and the workflow analyzes each opening in turn.
- `door-clip-evaluation`: the expected span for a clip with several labelled openings stops at the first gap of 10 s or more.
- `pipeline-debug-traces`: the door trace lists every opening, and a later opening's door event id resolves to its motion's trace.

## Impact

- `backend/src/fridgesense/door_events.py`: the open-span split, a per-opening record, stills, clip and analysis video, and the transaction.
- `backend/src/fridgesense/traces.py`: `openings` in `door.json`.
- `backend/src/fridgesense/handlers/api.py`: trace lookup from a `DOOR#…#<k>` id.
- `infra/lib/door-pipeline.ts`: a sequential Map over `$.openings` around Analyze → Save → HasRawClip. This needs a `cdk deploy` before it takes effect. That deploy is out of this change: it is Jayson's call.
- `backend/tests/clips/harness.py`: the expected span.
- The analysis prompt, the analysis-video encoding and Nova request code (`hand-evidence-analysis`) stay unchanged. They already read everything from the per-opening state.

Hackathon track: Ring (better door-event data from the Ring Partner API clip), AWS Builder (Step Functions Map).

**Out of scope:** de-duplicating an opening that continues into the next motion. In the real case, the second opening is also recorded by event 1792366818546, as it was before this change. Also out of scope: tuning the 10 s gap per device, and any PWA change.
