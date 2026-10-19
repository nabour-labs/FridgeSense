# Design

## Context

`door_events._fetch_stills` scores every clip frame (or still), calls `open_span()` once, and records one door event keyed by the window start. Everything after that comes from that single span: picks, `still_ms`, `clip.mp4` / `clip-raw.mp4` and `analysis.mp4` (from `hand-evidence-analysis`, already on `local`). The state machine then runs Analyze → Save → HasRawClip → BlurClip on one state. Downstream steps (`inventory.analyze_task`, `save_task`, `mark_failed_task`, the clip-blur Lambda) read `door_sk`, `still_keys`, `still_ms`, `clip` and `analysis_video` from the state they are given, never from the window start. The exception is the Nova trace, which writes under the motion's `debug/`.

## Goals / Non-Goals

**Goals:**
- Split the frames into openings at closed runs of 10 s or more, and record each opening exactly as one opening is recorded today.
- Leave single-opening motions unchanged: same keys, same top-level output, same state machine path.

**Non-Goals:**
- Merging an opening that runs into the next motion with that motion's event.
- Changes to the analysis prompt, the video encoding or the Nova request.
- PWA changes. The Activity list already shows one row per door event.

## Decisions

**Split rule: a closed run of 10 s or more, measured in time.** `open_spans(opened, times_ms, min_gap_ms=10_000)` replaces `open_span`. It walks the open indices and starts a new span when `times[next_open] − times[last_open + 1] ≥ 10 000`. Each span keeps today's shape: its first open index through the first index after its last open one. The rule is measured in time rather than frames, so it means the same on the clip path (500 ms) and the stills path (≥ 1 s). Why 10 s: people often block the zone for a second or two inside one opening, while a real close-and-reopen by someone else looks like the 73 s gap in the real case. The constant is `MIN_CLOSED_GAP_MS`, not a setting (keeping it small).
*Alternative:* counting frames. Rejected, because the meaning would change with `DOOR_FRAME_INTERVAL_MS`.

**One door event per opening, numbered keys.** Opening 1 keeps `DOOR#<iso start>#<device>` and `events/<start_ms>/`. Opening k ≥ 2 uses `#<k>` and `events/<start_ms>/opening-<k>/`. Keeping the window start in every key leaves the motion → door-event relation obvious, keeps the Activity order correct (suffixes sort right after opening 1), and the trace lookup only has to drop the suffix (`TRACE#` + the iso and device parts). An `event_ms`/prefix override travels in each opening's state, and `stills_prefix` callers (`store_blurred_stills`, `store_open_clip`, `store_analysis_video`) take it from there.
*Alternative:* key opening k by its own `opened_at`. Rejected: the trace lookup and the media prefix would no longer share the motion's time, and the stills prefix would no longer equal the motion folder that traces and the clip eval expect.

**One transaction for the claim and every door event.** The `RINGEVENT#…` claim plus N door-event Puts go into one `transact` call (N is at most a handful, far below DynamoDB's 100-item limit). A duplicate run therefore conflicts on the claim and writes nothing, as today, and deletes every `clip-raw.mp4` it uploaded.

**Per-opening media inside a loop.** The body of today's "door opening" branch (picks → blurred stills → open clip → status) becomes a function run once per span, which returns that opening's door-event item and state. The analysis video (`video_frame_indexes(span)` → `store_analysis_video`) runs per opening after the transaction, as today, under that opening's prefix. Suspect handling, alignment, learning and the trace stay once per motion.

**State machine: a sequential Map over `$.openings`.** `IsDoorOpening` → `Map(itemsPath $.openings, maxConcurrency 1, resultPath $.opening_results)`. The Map's iterator is Analyze → Save → HasRawClip → (BlurClip | DropRawClip) → `OpeningDone` (Pass, result `"ok"`). Analyze and Save catch to `MarkOpeningFailed` → `OpeningFailed` (Pass, result `"failed"`). After the Map, a `CheckOpenings` Pass sets `failed = States.ArrayContains($.opening_results, 'failed')`, and a Choice goes to `AnalysisFailed` (Fail) or `Done`. Running the openings sequentially keeps inventory updates in time order: opening 2's analysis sees opening 1's saved changes, and no two Saves race. The outer `MarkFailed` (FindWindow/FetchStills catch) is unchanged.
*Alternatives:* fail the whole Map when one item fails. Rejected: later openings would stay `analyzing`, which breaks "No door event left analyzing". Starting a separate execution per opening was also rejected: more IAM, and the openings would lose their order.

**Output shape.** `openings` holds the full per-opening states (each has `window`, `account_id` and the rest, so the existing task functions run unchanged). The top level is `{**state, **openings[0]-fields, "openings": [...]}`, so existing callers and tests that read `door_sk`, `still_keys`, `still_ms`, `clip` and `analysis_video` keep working.

**Traces.** `DoorTrace` gains `openings: list[dict]`. The top-level fields are filled from opening 1, and `door.json` gets `openings`. The Nova traces already sit under the motion's `debug/` with `run_ms`-unique names, so a second analysis adds files and `nova_calls` entries without overwriting the first.

**Clip eval harness.** `expected_span` stops at the first labelled gap of 10 s or more. The harness keeps reading opening 1 from the trace.

## Risks / Trade-offs

- [A second opening that continues past the window end is also recorded by the next motion, so it is analyzed twice] → Same as today. Out of scope and noted in the proposal.
- [The state machine change needs a deploy, and before it a Lambda deploy alone would emit `openings` that nothing reads] → The top-level fields still describe opening 1, so the old state machine keeps analyzing opening 1 and later openings stay `analyzing`. Deploy the stack (Lambda + state machine) together. One `cdk deploy` does that.
- [Larger state payload: N copies of the state] → A few KB per opening, well under the 256 KB limit.
- [A fixed 10 s gap could split a slow single opening where someone stands in front of the light for 10 s or more] → Each half is then analyzed separately. That costs one extra Nova call but loses no data, and the eval clips will show it if it happens.

## Migration Plan

No data migration: existing door events keep their keys. Deploy with `cdk deploy` (Jayson's call, not part of this change). Rollback: redeploy the previous commit. Any `#k` door events already written stay readable, because the API lists `DOOR#` by prefix.

## Test strategy

- **Unit** (`tests/test_open_spans.py`): `open_spans` on bool lists with times. Covers short versus long gaps, a gap of exactly 10 s, an opening at the end, no opening.
- **Task-level** (`tests/test_fetch_stills_split.py`, moto S3/DynamoDB, respx Ring, synthetic clips from `tests/clip_video.door_clip` with spans `[(1000, 6000), (18000, 24000)]` in a 30 s window): two door events with the spec's times and keys, stills per prefix, `clip-raw.mp4` and `analysis.mp4` per prefix with spans inside their own opening, `openings` output, per-opening `no_media`, duplicate re-run, and a brief gap still giving one event. The stills path uses the stubbed Ring still sequence from `test_fetch_stills_task`.
- **Trace / API** (`tests/test_door_traces.py`, `tests/test_api_debug.py`): `openings` in `door.json`, and lookup by a `#2` id.
- **Infra** (`infra/test/pipeline.test.ts`): Map with `ItemsPath $.openings` and `MaxConcurrency 1`, the iterator's Analyze/Save catches to `MarkOpeningFailed`, and `CheckOpenings` → `AnalysisFailed`/`Done`. The state-lookup helper flattens Map iterator states, so the existing assertions on Analyze/Save/BlurClip keep their meaning.
- **Clip eval** (`tests/clips/test_labels.py` or `test_evaluate.py`): `expected_span` with a 73 s gap.
- Nothing calls live Ring, AWS or Bedrock.
