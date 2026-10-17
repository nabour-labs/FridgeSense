# Design

## Context

- **Door check:** `door_events.fetch_stills` downloads 4–30 raw stills into memory and runs `DoorCheck.results` on them.
  - Each still gets only its best zone's `StillResult`.
  - It then computes `open_span` and `pick`, then crops, blurs and stores the picked stills as `still-<k>.jpg`.
  - Nothing else survives: not the raw stills, the other zones' values, or which still numbers were picked. A not-door motion leaves only a `motion_not_door` log line.
  - The rule comes from `door_calibration.setup_check`. It reads `DOORSETUP#<device>`, whose zones carry `baseline` (32×32 RGB raw bytes, not an image) and `ran_at`. The door references are `DOORREF#<device>#…` items holding the JPEG inline.
- **Analysis:** `inventory.analyze_task` loads the stored stills from S3 and the analysis references from DynamoDB (`REF#`), then calls `NovaAnalyzer.analyze`.
  - `analyze` builds one request with `build_request` and loops up to 2 attempts.
  - Per response, it logs `nova_cost` and calls `on_usage(tokens, usd)`.
  - It ignores `resp["metrics"]`, and it measures no time.
- **Storage:**
  - Bucket `fridgesense-stills-<acct>` has a 7-day expiration rule. The pipeline Lambda has read/write on it, and the API Lambda has read.
  - The table already has TTL on the attribute `ttl`.
- **API:** routes in `handlers/api.py` have only a `write` flag, which rejects viewers. Both API and PWA must work for a viewer (demo mode).

## Goals / Non-Goals

**Goals:**
- Capture the door check and Nova calls with no change to their decisions, outputs or timing beyond the extra writes.
- Make every image the owner sees the exact bytes that the rule or Nova saw.
- Add one backend module and one PWA screen, and keep the edits to existing modules to small seams.

**Non-Goals:**
- A general tracing framework (OpenTelemetry, X-Ray) or structured spans for other steps.
- Deduplicating images across traces (references are copied per trace).

## Decisions

### 1. Traces are files in S3 plus one summary item in DynamoDB

- **Choice:**
  - The full trace (`door.json`, `nova-<run_ms>-<n>.json`, images) goes to `…/events/<start_ms>/debug/`.
  - A `TRACE#<iso start>#<device>` item with `ttl` holds just enough for the list.
- **Why:**
  - Traces are large: tens of images and long text.
  - Under the event prefix they inherit the 7-day expiration for free.
  - The list must be cheap and paged by time, which the table already does for `DOOR#`.
  - The `TRACE#` sk shares its `<iso start>#<device>` suffix with `DOOR#…`, so a door event id maps straight to its trace (`GET /api/debug/motions/{door id}`) with no extra field on the door event.
- **Alternatives:**
  - Everything in DynamoDB: the 400 KB item limit, and images would bloat the table.
  - Listing S3 prefixes: no time-range query across devices, and slow.
  - CloudWatch logs: the `llm-usage-tracking` spec forbids prompts and images in logs, and they are not browsable from the PWA.

### 2. A `TraceWriter` passed into the existing steps, with a no-op when off

- **Choice:**
  - New `fridgesense/traces.py` with `TraceWriter(s3, table, bucket)` and `NullTraceWriter`.
  - `handlers/pipeline.py` builds one from `DEBUG_TRACES` (anything but `false` means on) and passes it as an optional argument to `fetch_stills` and `analyze_task`. It defaults to `NullTraceWriter`, so existing tests and call sites are unchanged.
  - Every public method wraps its own body in `try/except Exception` and logs `debug_trace_failed` with `part`. It never raises.
- **Why:** this keeps tracing out of the decision code paths, and it makes "tracing never breaks the pipeline" a property of one class that can be tested directly.
- **Alternative:** a module-level global or a decorator. Both are harder to stub per test, and a decorator can't see the intermediate values.

### 3. Door data: compute all zone values once and derive the verdict from them

- **Choice:**
  - Add `DoorCheck.zone_values(img) -> list[(zone, value, threshold, open)]`.
  - Reimplement `result` on top of it, picking the zone with max excess as today.
  - `fetch_stills` calls `zone_values` per still, builds the `StillResult` list from it, and assembles a `DoorTrace` dataclass. The dataclass holds the window, requested times, per-still entries (number, time, missing status, zones), the span, the picks, `stored_keys`, the outcome and the check.
  - It then calls `writer.door(state, raw, trace)` once, just before each `return`. That covers four exits: not_door, duplicate, no_media and door_open.
- **Why:** this measures each zone once (no double cost on up to 30 stills × zones) and guarantees that the trace shows the same numbers the decision used.
- **Missing status:** `download_stills` currently drops the missing stills. It gains a variant that returns `(n, bytes | None, status)` so the trace can show `missing_status`. The existing return shape stays for the old callers.
- **Rule and references:** the writer gets them from the `DoorCheck` (zones, features, thresholds, baselines, `source`). For `setup` checks it also gets `ran_at` and the reference list from `door_calibration`. `DoorCheck` gains optional `ran_at` and `references` fields, which `setup_check` fills.
  - The baselines are rendered to PNG (32×32 scaled ×8, nearest neighbour) when written.
  - Each reference JPEG is copied as `door-ref-<id>.jpg`.
- **Raw stills:** they are written in parallel (the same 8-worker pool size as the downloads), so a 30-still motion adds roughly 1–2 s to a step that has a 90 s timeout.

### 4. Nova data: an `on_call` callback on `NovaAnalyzer.analyze`

- **Choice:**
  - `analyze` gains `on_call: Callable[[CallRecord], None] | None`.
  - Around each `client.converse(**request)` it measures `time.perf_counter()` and builds a `CallRecord(attempt, request, response | None, error_code | None, tokens, usd, latency_ms, wall_ms, outcome)`.
  - It calls `on_call` before it raises or returns. Error paths call it too, then raise as today.
  - `analyze_task` sets `run_ms = clock()` once per task run and passes `on_call=lambda rec: writer.nova(state, run_ms, rec, references, still_keys)`.
- **Serializing the request:**
  - The writer walks `request["messages"][0]["content"]`. Each image block is replaced by `{"type": "image", "role", "n", "key"}`. Stills map to `state["still_keys"][n-1]` (the stored, blurred object that was sent). References are written to `nova-<run_ms>-ref-<n>.jpg` once per run, which records the reference bytes as sent even if the owner edits them later.
  - Text blocks become `{"type": "text"}`, and `cachePoint` becomes `{"type": "cache_point"}`.
  - `inferenceConfig` and `toolConfig` are kept as is.
- **Serializing the response:** the response is reduced to `output`, `stopReason`, `usage` and `metrics`, dropping `ResponseMetadata`.
- **Summary item:** `nova_calls` is appended with `list_append` through `table.update`.
- **Alternative:** wrapping the Bedrock client in a recording proxy. It would capture the requests, but it can't tell stills from references or know the S3 keys, and it would hide errors from the analyzer's own handling.

### 5. Owner-only routes through a new `owner` flag on `route`

- **Choice:** `route(method, path, write=False, owner=False)`. The handler returns 403 `{"error": "read-only"}` when `(write or owner) and role != "owner"`, which matches the existing viewer error.
  - The routes are `GET /api/debug/motions` and `GET /api/debug/motions/{id}`.
  - The list reuses `_event_range` with a `TRACE#` prefix (generalized to take the prefix), and reuses the `limit`/`cursor` logic.
  - The detail reads `door.json` and `nova-*.json` (listing `debug/nova-` under the prefix, sorted by `run_ms` then attempt) and swaps every `key` for a presigned URL with `STILL_LINK_TTL_S`.
  - `door.json` missing (`NoSuchKey`) means 404.
- **Why:** the raw stills are unblurred, so viewers (demo mode) must never get links to them.
- **Ids:** `encode_id("TRACE#…")`. The detail also accepts `encode_id("DOOR#…")` and rewrites the prefix.

### 6. PWA: one `Debug.tsx` screen with list and detail, and hash routing inside Config

- **Choice:**
  - `Config.tsx` adds `{id: "debug", label: "Debug", hash: "#config/debug"}`, shown only when `role === "owner"`.
  - `sectionFromHash` matches `#config/debug` and `#config/debug/<id>`. Viewers on a debug hash fall back to "refs".
  - The grid uses `grid-cols-4` for the owner and `grid-cols-3` for a viewer, with short labels that can wrap.
  - `Debug.tsx` reuses Activity's day picker and paging, `Sheet` for full-size images, and `ImageMarkup` (read-only) to draw zone boxes on the raw stills.
  - Activity's `EventCard` gets a small "Debug" link for the owner.
- **Polling:** the list does not poll. The detail loads once, plus a manual "Refresh" while a call is still running.
- **Mock API:** `mock-api.ts` adds the two routes with SVG stills, so the screen can be built in the preview.

## Risks / Trade-offs

- **Unblurred stills of people stored for 7 days** → Owner-only API, 7-day expiry, and `DEBUG_TRACES=false` to stop it. The spec carve-out is explicit. The default is on because the owner asked for it. The demo should be recorded with it off, or with no one in frame.
- **Extra S3 writes slow the fetch-stills step** → The writes are parallel. The JSON is written last, so a timeout leaves partial images but no `door.json`, and the API returns 404 for that motion rather than a broken trace.
- **Trace drift from the decision** → The trace is built from the same `zone_values` the verdict uses, and the tests assert that `door.json`'s per-still `open` equals the outcome's span.
- **Large `door.json` or detail payload with 30 stills and presigned URLs** → Roughly 30 × 400 bytes of URL plus the zones, well under the API Gateway limit.
- **`nova_calls` list growth** → At most 2 attempts × Step Functions retries (≤ 3), so ≤ 6 entries.
- **Cost of the copied references** → Each copy is ≤ 300 KB and there are a handful per analysis. That is negligible next to the stills.

## Migration Plan

1. Deploy the pipeline and API Lambdas with `DEBUG_TRACES` unset (on). No table or bucket change is needed: TTL on `ttl` and the 7-day lifecycle already exist.
2. Motions from before the deploy have no trace. The API returns 404, and the PWA shows "expired or never recorded".
3. Rollback: set `DEBUG_TRACES=false` (or redeploy the previous code). Existing traces expire on their own within 7 days.

## Test strategy

- **Unit (pytest, `backend/tests/test_traces.py`):**
  - `TraceWriter` against moto S3 and DynamoDB: file layout, the `door.json` shape for each outcome, PNG baselines, reference copies, the `ttl` value, `nova_calls` append.
  - Failure isolation: a stubbed S3 that raises `AccessDenied` must produce `debug_trace_failed` and no exception.
  - `NullTraceWriter` writes nothing.
- **Unit (`test_door_check.py`):** `zone_values` for both directions and the inclusive threshold, and that `result` still matches the existing scenarios.
- **Unit (`test_analysis_request.py`/`test_analysis_response.py`):**
  - `on_call` gets one `CallRecord` per attempt with tokens, `latency_ms` from the stubbed `metrics`, and `wall_ms` from an injected `perf_counter` stub.
  - Invalid-then-valid gives two records.
  - `ClientError` and `ReadTimeoutError` give an error record, then the usual raise.
  - Bedrock is stubbed with botocore Stubber or the fake client used today, plus new fixtures `tests/fixtures/nova/converse_tool_use_metrics.json` and `converse_end_turn_metrics.json` that include `metrics.latencyMs`.
- **Integration (`test_fetch_stills_task.py`, `test_analyze_task.py`, `test_pipeline_e2e.py`):**
  - The existing Ring fixtures and fake Ring and HTTP clients, moto S3 and DynamoDB, the Rekognition stub, and the face fixtures.
  - They assert the traces for not_door, door_open, no_media and duplicate, the raw bytes equal to the downloaded bytes, the analysis still receiving blurred bytes, and `DEBUG_TRACES=false` writing nothing.
- **Contract (`test_api_debug.py`):** the list, detail by TRACE id and by DOOR id, 404 for untraced and expired, 400 for bad ids and ranges, 403 for a viewer, and presigned URLs present (moto).
- **PWA (Vitest + Testing Library):**
  - `client.test.ts` covers paths and query strings.
  - `Config.test.tsx` covers the Debug tab and viewer hiding.
  - `Debug.test.tsx` covers the list rows, detail sections, missing still, default rule, failed and invalid calls, and 404.
  - `Activity.test.tsx` covers the owner and viewer Debug link.
  - The API is stubbed as in the existing screen tests.
- **Infra (`infra/test/pipeline.test.ts`):** the pipeline Lambda has a `DEBUG_TRACES` env var.
- **Never live:** no Ring, AWS or Bedrock calls in any test.
