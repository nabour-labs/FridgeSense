# pipeline-debug-traces Specification

## Purpose
Keeps, for 7 days, a per-motion record of what the door check and the Nova analysis saw, decided, spent and how long they took, so the owner can see why the app judged a motion the way it did.

## Requirements

### Requirement: Door trace for every motion
When `DEBUG_TRACES` is not `false`, the fetch-stills step SHALL write a door trace for every motion it handles, whatever the outcome (`door_open`, `not_door`, `no_media`, `duplicate`). Files go under `accounts/<account_id>/devices/<device_id>/events/<start_ms>/debug/`: each downloaded still as `raw-<n>.jpg` (bytes as downloaded) and `door.json`.

#### Scenario: Motion that is not the door
- **WHEN** 4 stills are downloaded for window start `1786715596000` and every zone stays below its threshold
- **THEN** `raw-1.jpg` … `raw-4.jpg` and `door.json` exist under `accounts/A1/devices/D1/events/1786715596000/debug/`, `door.json` has `outcome = "not_door"`, and no door event is saved

#### Scenario: Door opening
- **WHEN** a motion is a door opening and its picked stills are stored
- **THEN** `door.json` has `outcome = "door_open"`, the `door_sk`, `opened_at`, `closed_at`, `picked` (still numbers) and `stored_keys` equal to the door event's `still_keys`

#### Scenario: Raw stills are the downloaded bytes
- **WHEN** a downloaded still contains a face and the door check passes
- **THEN** `raw-<n>.jpg` is byte-for-byte the downloaded still, while `still-<k>.jpg` sent to analysis is still the cropped, blurred still

#### Scenario: Too few stills
- **WHEN** only 1 of 4 stills downloads and Ring answered 403 for the other three
- **THEN** `door.json` has `outcome = "no_media"`, still 1 has a `key`, and stills 2–4 have `key = null` and `missing_status = 403`

#### Scenario: Duplicate run
- **WHEN** a second run for the same Ring event ends with `duplicate`
- **THEN** its trace is written with `outcome = "duplicate"` and replaces the earlier trace's summary item for that motion

### Requirement: Per-still scores in the door trace
`door.json` SHALL list each requested still as `{"n", "at_ms", "key", "missing_status", "zones": [{"zone", "value", "threshold", "open"}], "best_zone", "open"}`. It gives every zone's feature value rounded to 4 places, that zone's threshold, and whether that value counts as open. `open` for the still is the best zone's verdict, as the door check used it. `open_span` lists the still numbers in the span, or is empty.

#### Scenario: Two zones scored
- **WHEN** default zones with threshold 0.02 are used and still 2's colorful fraction is 0.0031 in zone 1 and 0.0512 in zone 2
- **THEN** still 2 has `zones = [{"zone": 1, "value": 0.0031, "threshold": 0.02, "open": false}, {"zone": 2, "value": 0.0512, "threshold": 0.02, "open": true}]`, `best_zone = 2` and `open = true`

#### Scenario: Span and picks
- **WHEN** of 10 stills, 3 to 6 are open and 7 is closed
- **THEN** `open_span = [3, 4, 5, 6, 7]` and `picked` lists at most 4 still numbers from that span

#### Scenario: Below-direction rule
- **WHEN** a setup zone uses `brightness` with `direction = "below"` and threshold 0.4, and a still's value there is 0.35
- **THEN** that zone entry has `open = true`

### Requirement: Deciding rule in the door trace
`door.json` SHALL have `rule = {"source", "ran_at", "zones", "references"}`. Each zone is `{"zone", "box", "feature", "direction", "threshold", "margin", "baseline_key"}`. For `setup`, each zone's baseline is stored as `baseline-<zone>.png`. Each door reference the setup learned from is stored as `door-ref-<id>.jpg`, listed with its `status` and `box`. For `default`, `ran_at`, `margin` and `baseline_key` are null and `references` is empty.

#### Scenario: Setup rule
- **WHEN** the device has a setup run at `2026-10-15T20:00:00Z` with 2 zones and 3 door references (2 closed, 1 open)
- **THEN** `rule.source = "setup"`, `rule.ran_at = "2026-10-15T20:00:00Z"`, both zones list feature, direction, threshold, margin and a `baseline_key` whose PNG exists, and `rule.references` has 3 entries whose `key` objects exist

#### Scenario: Default rule
- **WHEN** the device has no setup
- **THEN** `rule.source = "default"`, the zones are the `DOOR_ZONES` boxes with `feature = "blue"`, `direction = "above"` and the `DOOR_THRESHOLD`, and `rule.references = []`

#### Scenario: Setup lookup failed
- **WHEN** loading the setup raises an error and the default rule is used
- **THEN** `rule.source = "default"`

### Requirement: Nova call trace
When `DEBUG_TRACES` is not `false`, each Converse attempt of a door opening's analysis SHALL write `nova-<run_ms>-<attempt>.json` in the event's `debug/` folder. It holds `request.content` in request order: text blocks `{"type": "text", "text"}`, images `{"type": "image", "role": "reference" | "still", "n", "key"}` and `{"type": "cache_point"}`. It also holds `model_id`, `inferenceConfig`, `toolConfig` and the raw `response` (`output`, `stopReason`, `usage`, `metrics`).

#### Scenario: Request with references
- **WHEN** an analysis sends 2 reference images (annotations "oat milk", "eggs") and 4 stills with the inventory `[milk]`
- **THEN** `request.content` lists, in order: the reference header, "Reference 1: oat milk", image reference 1, "Reference 2: eggs", image reference 2, then "Image 1 of 4", image still 1 … "Image 4 of 4", image still 4, then the instruction text containing `Current inventory: [milk]`

#### Scenario: Image keys are retrievable
- **WHEN** that request is traced
- **THEN** each still image's `key` is the stored `still-<n>.jpg` sent to Nova, and each reference image's `key` is a `nova-<run_ms>-ref-<n>.jpg` object holding the exact reference bytes sent

#### Scenario: Owner's instructions shown
- **WHEN** the owner's instructions are "Ignore condiments"
- **THEN** the final text block contains `Owner's instructions: Ignore condiments`

#### Scenario: Response kept
- **WHEN** Nova answers with tool input `{"added": [{"item": "milk", ...}], "removed": []}` and `stopReason = "tool_use"`
- **THEN** the trace's `response.output` holds that tool input and `response.stopReason = "tool_use"`

### Requirement: Tokens, cost and latency per Nova call
Each Nova call trace SHALL have `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `usd` (as `llm_usage` computes them), `latency_ms` (Converse `metrics.latencyMs`, or null when absent) and `wall_ms` (measured time of the call, whole ms). The motion's summary item SHALL append the same numbers per attempt, with `attempt`, `outcome` (`ok`, `invalid`, `error`) and the trace `key`.

#### Scenario: Valid answer
- **WHEN** a call returns `usage = {inputTokens: 1180, outputTokens: 96, cacheReadInputTokens: 2000}` and `metrics = {latencyMs: 2140}` after 2310 ms
- **THEN** the trace has `input_tokens = 1180`, `output_tokens = 96`, `cache_read_tokens = 2000`, `cache_write_tokens = 0`, `usd = 0.000818`, `latency_ms = 2140` and `wall_ms = 2310`, and the summary's `nova_calls` gets one entry with `outcome = "ok"`

#### Scenario: Invalid answer then valid
- **WHEN** the first answer has no tool use and the second is valid
- **THEN** two traces are written, `nova-<run_ms>-1.json` with `outcome = "invalid"` and `nova-<run_ms>-2.json` with `outcome = "ok"`, and `nova_calls` has two entries

#### Scenario: Call that raises an error
- **WHEN** Converse raises `ThrottlingException` after 120 ms
- **THEN** a trace is written with `outcome = "error"`, `error_code = "ThrottlingException"`, `response = null`, all token counts 0, `usd = 0`, `latency_ms = null` and `wall_ms = 120`, and the step still raises its usual retryable error

#### Scenario: Retried analyze step
- **WHEN** the analyze step runs twice for one door opening (the workflow retried it)
- **THEN** each run's attempts get a different `run_ms`, and no trace file is overwritten

### Requirement: Listable trace summaries that expire
Each traced motion SHALL have one item `pk = ACCOUNT#<account_id>`, `sk = TRACE#<iso start>#<device_id>`, holding `device_id`, `ring_event_id`, `start_ms`, `end_ms`, `outcome`, `zones_source`, `best` (`value`, `zone`, `feature`, `threshold`), `stills_requested`, `stills_downloaded`, `door_sk` (or null), `nova_calls` and `ttl`. `ttl` is epoch seconds 7 days after the window start, so DynamoDB TTL removes the item when the S3 files expire.

#### Scenario: Summary written
- **WHEN** a not-door motion with window start `1786715596000` on device D1 is traced
- **THEN** item `TRACE#2026-08-14T13:53:16.000Z#D1` exists with `outcome = "not_door"`, `door_sk = null`, `nova_calls = []` and `ttl = 1787320396`

#### Scenario: Nova calls added later
- **WHEN** the analysis of that motion's door opening makes one call
- **THEN** the same summary item's `nova_calls` gains one entry, and its other fields are unchanged

### Requirement: Tracing never breaks the pipeline
A failure to write any trace file or summary SHALL be logged as a `debug_trace_failed` warning with `account_id`, `device_id`, the part (`door`, `nova`, `summary`) and the error name. The step's outcome, the door event, the analysis result and the usage totals SHALL be the same as without tracing.

#### Scenario: S3 put fails during door trace
- **WHEN** writing `raw-2.jpg` raises `AccessDenied` for a door opening
- **THEN** a `debug_trace_failed` warning with `part = "door"` is logged, the door event is saved with `status = "analyzing"`, and the run continues to analysis

#### Scenario: Summary write fails during analysis
- **WHEN** appending to `nova_calls` raises an error during a valid analysis
- **THEN** a `debug_trace_failed` warning with `part = "summary"` is logged and the analysis result, `nova_usd` and the `USAGE#` totals are saved as usual

### Requirement: Tracing can be turned off
When `DEBUG_TRACES` is `false`, the pipeline SHALL write no `debug/` objects and no `TRACE#` items, and SHALL behave exactly as it does without this capability.

#### Scenario: Off
- **WHEN** `DEBUG_TRACES=false` and a door opening is analyzed
- **THEN** no object exists under the event's `debug/` prefix and no `TRACE#` item exists

### Requirement: List motions over HTTP
`GET /api/debug/motions` SHALL return `{"motions": [...], "next"}`, newest first. Each entry has `id`, `device_id`, `at` (ISO window start), `outcome`, `best`, `stills_downloaded`, `door_event_id` (or null), and `nova` totals `{calls, input_tokens, output_tokens, usd, latency_ms}` (sum over calls, latency summed over non-null values). Range and paging rules SHALL be the same as `GET /api/events`. Viewers SHALL get 403.

#### Scenario: Listing
- **WHEN** a door opening with two Nova calls (1180/96 tokens, 2140 ms and 1200/90 tokens, 1900 ms) and a not-door motion an hour later are traced today
- **THEN** the not-door motion is listed first with `nova.calls = 0`, and the door opening has `nova.calls = 2`, `input_tokens = 2380`, `output_tokens = 186` and `latency_ms = 4040`

#### Scenario: Viewer refused
- **WHEN** a viewer token calls `GET /api/debug/motions`
- **THEN** the response is 403 `{"error": "read-only"}`

#### Scenario: Bad range
- **WHEN** `days=0` or `limit=51`
- **THEN** the response is 400

### Requirement: Read one trace over HTTP
`GET /api/debug/motions/{id}` SHALL accept a motion `id` or a door event `id` and return the summary plus `door` (the `door.json` content) and `nova` (each call trace, in attempt order). Every `key` SHALL be replaced by a `url`, a 15-minute download link. It returns 404 when no trace exists or its files have expired. Viewers SHALL get 403.

#### Scenario: Trace by door event id
- **WHEN** the owner requests the id of a door event from `GET /api/events` whose motion was traced
- **THEN** the response has `door.stills` with a `url` per downloaded still, `door.rule.zones[*].baseline_url`, and `nova[*].request.content` image entries with `url`s that download the images without other credentials

#### Scenario: Untraced event
- **WHEN** the owner requests the id of a door event recorded before tracing existed
- **THEN** the response is 404 `{"error": "no trace"}`

#### Scenario: Files expired
- **WHEN** the summary item still exists but `door.json` is gone from S3
- **THEN** the response is 404 `{"error": "no trace"}`

#### Scenario: Viewer refused
- **WHEN** a viewer token calls `GET /api/debug/motions/{id}`
- **THEN** the response is 403 and no link is generated

#### Scenario: Bad id
- **WHEN** the id does not decode to a `TRACE#` or `DOOR#` key
- **THEN** the response is 400
