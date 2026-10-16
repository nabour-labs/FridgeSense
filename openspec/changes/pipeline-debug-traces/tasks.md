# Tasks

## 1. Door check exposes every zone's value

- [x] 1.1 Write failing tests in `backend/tests/test_door_check.py`:
  - `zone_values` returns `(zone, value, threshold, open)` for every zone ("Two zones scored").
  - Below-direction rule ("Below-direction rule").
  - The threshold is inclusive.
  - Run them and confirm they fail because `zone_values` does not exist.
- [x] 1.2 Add `DoorCheck.zone_values` and rebuild `result` on top of it. Verify the 1.1 tests and every existing door-check test pass unchanged.
- [x] 1.3 Write failing tests for a `download_stills` variant that returns `(n, bytes | None, missing_status)` for every requested still. Cover 403, 416 after retries, and a Ring/OAuth error giving `None`. Implement it, keep the old function's return shape for existing callers, and verify both test sets pass.

## 2. Trace writer: door traces

- [x] 2.1 Write failing tests in `backend/tests/test_traces.py` (moto S3 + DynamoDB) for `TraceWriter.door`:
  - `raw-<n>.jpg` equals the input bytes.
  - `door.json` has per-still `zones`, `best_zone`, `open`, `open_span`, `picked` and `stored_keys` ("Door opening", "Span and picks").
  - Missing stills have `key = null` and `missing_status` ("Too few stills").
  - The `TRACE#<iso>#<device>` summary has the spec fields and `ttl = start_s + 604800` ("Summary written").
- [x] 2.2 Implement `fridgesense/traces.py`: the `DoorTrace` dataclass, `TraceWriter.door` (parallel raw-still puts, then `door.json`, then the summary item) and `NullTraceWriter`. Verify that the 2.1 tests pass.
- [x] 2.3 Write failing tests for the deciding rule:
  - "Setup rule": zones carry feature, direction, threshold, margin and `baseline_key`. `baseline-<z>.png` is a valid PNG of the 32×32 baseline. `door-ref-<id>.jpg` matches the `DOORREF#` image bytes. `ran_at` is set.
  - "Default rule" has no baselines and no references.
- [x] 2.4 Make `setup_check` fill the optional `ran_at` and `references` on `DoorCheck`, and render baselines to PNG in the writer. Verify that the 2.3 tests and the existing `test_door_calibration.py` tests pass.
- [x] 2.5 Write failing tests for "Tracing never breaks the pipeline" (door part):
  - An S3 stub raising `AccessDenied` on a put leads to a `debug_trace_failed` log with `part = "door"` and no exception.
  - A summary put failure leads to `part = "summary"`.
  - Implement the try/except logging in each writer method and verify.

## 3. Wire door traces into fetch-stills

- [x] 3.1 Write failing tests in `backend/tests/test_fetch_stills_task.py`, using the existing Ring fixtures, fake clients, moto and the Rekognition stub:
  - "Motion that is not the door": the trace is written and no door event is saved.
  - "Door opening": `stored_keys` equals `still_keys`.
  - "Raw stills are the downloaded bytes": a face fixture, raw bytes equal the download, and `still-<k>.jpg` is blurred.
  - "Too few stills" with 403s.
  - "Duplicate run".
  - "Setup lookup failed" gives `rule.source = "default"`.
  - "Debug copy is not an event still": face detection fails for still 2, so `raw-2.jpg` exists but `still_keys` doesn't list it.
  - "S3 put fails during door trace": the door event is still saved as `analyzing`.
  - "Off": `DEBUG_TRACES=false` (`NullTraceWriter`) writes no `debug/` objects and no `TRACE#` items.
- [x] 3.2 Add an optional `writer` argument to `fetch_stills`:
  - Build the per-still entries from `zone_values` and the download variant.
  - Call `writer.door(...)` before each return.
  - Build the writer in `handlers/pipeline.py` from `DEBUG_TRACES`.
  - Verify the 3.1 tests and all existing fetch-stills, door-check and pipeline tests pass.

## 4. Nova call records

- [x] 4.1 Nova fixtures with `metrics.latencyMs`: the existing `tests/fixtures/nova/converse_tool_use.json` (2140 ms) and `converse_end_turn.json` (1900 ms) already carry it, so no copies are needed. The "metrics absent" case deletes the field in the test.
- [x] 4.2 Write failing tests in `backend/tests/test_analysis_response.py` for `NovaAnalyzer.analyze(on_call=...)`:
  - "Valid answer": tokens, `usd = 0.000818`, `latency_ms = 2140`, and `wall_ms` from an injected clock.
  - "Invalid answer then valid": two records with `outcome` `invalid`, then `ok`.
  - "Call that raises an error": `ThrottlingException` gives an error record, then `BedrockRetryable`. `ReadTimeoutError` behaves the same.
  - `metrics` absent gives `latency_ms = None`.
- [x] 4.3 Implement `CallRecord` and the `on_call` callback, with timing via an injectable `perf_counter`. Verify the 4.2 tests and all existing analysis, usage and `llm_usage` tests pass unchanged, including "No content in the log".

## 5. Trace writer: Nova traces

- [x] 5.1 Write failing tests in `test_traces.py` for `TraceWriter.nova`:
  - "Request with references": content order with text, image and cache_point entries.
  - "Image keys are retrievable": still keys equal the stored keys, and `nova-<run_ms>-ref-<n>.jpg` equals the reference bytes sent, written once per run.
  - "Owner's instructions shown".
  - "Response kept": `output` and `stopReason`, no `ResponseMetadata`.
  - "Nova calls added later": the summary's `nova_calls` gets one entry and the other fields are unchanged.
  - "Summary write fails during analysis" gives `debug_trace_failed` with `part = "summary"`.
- [x] 5.2 Implement `TraceWriter.nova`: request serialization, reference copies, `nova-<run_ms>-<attempt>.json`, and the `list_append` on the summary. Verify that the 5.1 tests pass.
- [x] 5.3 Write failing tests in `backend/tests/test_analyze_task.py`:
  - "Retried analyze step": two task runs give different `run_ms` values and no overwrite.
  - "Analysis receives blurred bytes": still 1's bytes in the request equal the stored blurred object, not `raw-1.jpg`.
  - A summary failure leaves the analysis result, `nova_usd` and the `USAGE#` totals unchanged.
  - "Off" writes no `nova-*` objects.
- [x] 5.4 Wire `on_call` in `inventory.analyze_task` through an optional `writer` argument, with `run_ms = clock()`, and pass the writer from `handlers/pipeline.py`. Verify the 5.3 tests and `test_pipeline_e2e.py` pass, then add one end-to-end assertion that a full run leaves `door.json`, `nova-*-1.json` and a summary with one `nova_calls` entry.

## 6. API routes

- [x] 6.1 Write failing tests in `backend/tests/test_api_debug.py`, using `api_helpers` and moto:
  - "Listing": order, `nova` totals 2380/186/4040 ms, and `calls = 0` for a not-door motion.
  - "Viewer refused" for both routes, with no presign call.
  - "Bad range" (`days=0`, `limit=51`) and paging with `limit`/`cursor`.
  - "Trace by door event id": stills, baseline and Nova image entries have `url` and no `key`.
  - "Untraced event" and "Files expired" give 404 `{"error": "no trace"}`.
  - "Bad id" gives 400.
- [x] 6.2 Add the `owner` flag to `route`, generalize `_event_range` to take a sort-key prefix, and implement `GET /api/debug/motions` and `GET /api/debug/motions/{id}`. Verify that the 6.1 tests and every existing API test pass, then refactor with tests green.

## 7. PWA

- [x] 7.1 Add `debugMotions(from, to, limit, cursor)` and `debugMotion(id)` to `api/client.ts`, and add `DebugMotion`, `MotionTrace`, `DoorTrace` and `NovaCall` to `api/types.ts`. Write failing tests in `client.test.ts` for the paths and query strings first, then verify they pass.
- [x] 7.2 Add the two debug routes to `pwa/scripts/mock-api.ts` with one door-opening trace (6 SVG stills, setup rule, 2 Nova calls including one invalid) and one not-door trace.
- [x] 7.3 Write failing tests in `Config.test.tsx`:
  - "Switch to debug".
  - "Viewer sees read-only config": no Debug tab.
  - "Viewer opens the debug link": falls back to refs, no request.
  - The existing tab tests still pass.
  - Then add the owner-only fourth tab and the `#config/debug[/<id>]` hash handling to `Config.tsx` and `App.tsx`, and verify.
- [x] 7.4 Write failing tests in `screens/Debug.test.tsx` for:
  - "Not-door row", "Door opening row", "No motions" and "Open a motion".
  - "Door section", "Picked stills marked", "Missing still", "Default rule" and "Missing detail".
  - "Request in order", "Numbers shown", "Failed call" and "Invalid answer".
- [x] 7.5 Implement `screens/Debug.tsx` (list with day picker and paging, detail with door and Nova sections, `Sheet` viewer, read-only `ImageMarkup` zone boxes). Verify that the 7.4 tests pass and that `npm test` passes in `pwa/`.
- [ ] 7.6 Write failing tests in `Activity.test.tsx` for "Owner follows the link" and "Viewer has no link". Add the link to `EventCard` and verify.
- [ ] 7.7 In the browser preview against the mock API, check:
  - The four tabs fit at 375 px with no horizontal scroll ("Four tabs fit a phone").
  - The list and detail render in light and dark.
  - Images open full size.
  - The Activity "Debug" link lands on the right trace.

## 8. Infra, docs and checks

- [ ] 8.1 Write a failing test in `infra/test/pipeline.test.ts` that asserts the pipeline Lambda has `DEBUG_TRACES` (from a `debugTraces` context value, default `"true"`). Add it in `door-pipeline.ts` and `fridgesense-stack.ts`, then verify that `npm test` passes in `infra/`.
- [ ] 8.2 Add a short "Debug traces" section to the README covering:
  - what is kept and for how long;
  - that the raw stills are unblurred and owner-only;
  - how to turn traces off with `DEBUG_TRACES=false` / `-c debugTraces=false`.
  - If any AWS step hit friction, add a `docs/friction-log.md` entry; otherwise add nothing.
- [ ] 8.3 Run all suites and linters green, then report the commands and their results:
  - `cd backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
  - `cd pwa && npm test && npm run build`
  - `cd infra && npm test`
- [ ] 8.4 Run `cdk diff` and ask Jayson before `cdk deploy`. After the deploy, open the fridge door once and wave at the camera once without opening the door. Confirm that both motions appear in Config → Debug, that the door opening shows its raw stills, scores, rule and Nova call with tokens and latency, and that the Activity "Debug" link opens it.
