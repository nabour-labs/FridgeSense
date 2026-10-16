# Proposal

## Why

When the app gets a door opening wrong (it misses one, invents one, or Nova lists the wrong items), today there is no way to see why. The door check's per-still scores, the raw stills it looked at, the Nova request and the Nova response are all thrown away. Only a `nova_usd` total and some log lines survive. Tuning the door setup and the analysis prompt before the demo needs a way to look at each motion and see exactly what the pipeline saw, decided and paid.

## What Changes

- **Door trace for every motion**, including motions judged "not the door" and motions with too few stills. A trace holds:
  - every raw still the door check downloaded, stored as downloaded (unblurred);
  - each still's value for every zone, its best zone, and its open/closed verdict against that zone's threshold;
  - the open span, the stills picked for analysis and their stored (cropped and blurred) keys;
  - the outcome;
  - the rule that decided: `setup` or `default`. For `setup`, it also holds each zone's box, feature, direction, threshold, margin and baseline image, plus the door reference images the setup learned from.
- The door check is a pixel rule, not an LLM, so the door trace has no prompt and no reasoning text. Its "reasoning" is the per-still, per-zone scores against thresholds.
- **Nova trace for every Converse attempt** of a door opening's analysis. It holds:
  - the full request: every text block (header, reference annotations, "Image n of N", the instructions with the inventory and the owner's instructions), every image in order (reference images and stills), cache points, and the inference and tool config;
  - the raw response: `output`, `stopReason` and `usage`;
  - input, output, cache-read and cache-write tokens, and `usd`;
  - latency: Bedrock's `metrics.latencyMs` and the measured wall time.
  - Failed attempts are traced with their error code and wall time.
- **Storage:**
  - Trace files go to S3 under the event's existing prefix, in `debug/`, so the bucket's 7-day expiry removes them.
  - One DynamoDB `TRACE#` summary item per motion makes traces listable. Its `ttl` makes DynamoDB remove it after 7 days.
  - Writing a trace never fails or delays the pipeline beyond the writes themselves.
  - Traces are on by default and can be turned off with `DEBUG_TRACES=false`.
- **API (owner only, since traces hold unblurred stills):**
  - `GET /api/debug/motions` lists motions newest first, paged like `/api/events`.
  - `GET /api/debug/motions/{id}` returns one trace with 15-minute image links. `{id}` is a motion id or a door event id.
  - Viewers get 403.
- **PWA:**
  - A fourth Config tab, "Debug", at `#config/debug`, lists every motion with its outcome, best score and Nova tokens, cost and latency.
  - `#config/debug/<id>` shows one motion: the door trace as a grid of raw stills with scores and verdicts, the setup zones, baselines and references, then each Nova call with its images in request order, the text blocks, the response JSON, tokens and latency.
  - On Activity, the owner gets a "Debug" link on each door opening.
  - Viewers see neither the tab nor the links.
- **Spec carve-out (BREAKING for a privacy rule):** "an unblurred still SHALL never be stored" gets one exception. Debug traces store raw stills under `debug/` with the 7-day expiry, only when `DEBUG_TRACES` is on, and serve them only to the owner. The stills sent to Nova stay blurred.

## Capabilities

### New Capabilities

- `pipeline-debug-traces`: per-motion records of what the door check and the Nova analysis saw, decided, spent and how long they took, how they are stored and expire, and how the owner reads them over the API and in the app.

### Modified Capabilities

- `door-event-detection`: "Fail closed when face detection fails" and "Only blurred stills are analyzed" allow the owner-only, 7-day raw debug stills. Stills sent to analysis are unchanged.
- `inventory-app`: "Config screen" goes from three tabs to four, adding "Debug". New requirements cover the Debug tab, the motion detail view and the Activity "Debug" link.

`llm-usage-tracking` is unchanged: `llm_usage` log events still carry no prompt text or image bytes. Prompts and images go only to the owner-only S3 trace.

## Impact

- **Backend:**
  - New `backend/src/fridgesense/traces.py`, which builds and writes traces and reads them for the API.
  - `door_events.fetch_stills` collects per-zone values and hands a trace to the writer. `DoorCheck` gains a per-zone values method.
  - `analysis.NovaAnalyzer.analyze` reports each attempt's request, response, error and timing through a callback.
  - `inventory.analyze_task` wires that callback to the trace writer.
  - `handlers/pipeline.py` builds the writer from env.
  - `handlers/api.py` gains two owner-only GET routes and a route-level `owner` flag.
- **PWA:**
  - `screens/Config.tsx` gets a fourth tab.
  - New `screens/Debug.tsx` (list and detail).
  - `screens/Activity.tsx` gets the owner's "Debug" link.
  - `api/client.ts` and `api/types.ts` get the new calls and types.
  - The mock API serves sample traces.
- **Infra:**
  - None for TTL: the table already expires items on `ttl`.
  - `DEBUG_TRACES` env on the pipeline Lambda.
  - No new IAM: the pipeline already reads and writes the bucket, and the API already reads it.
- **Cost:**
  - Per motion: up to 30 raw stills of a few hundred KB each, plus a few JSON files (S3 PUTs at about $0.005 per 1,000), and one or two small DynamoDB writes.
  - Per Nova attempt: one JSON write plus the reference images.
  - No extra Rekognition or Bedrock calls.
- **Order:** this change edits the "Config screen" requirement as `fridge-crop-box` leaves it, so `door-zone-setup` and then `fridge-crop-box` must be archived first.

**Hackathon tracks:** AWS Builder (S3, DynamoDB TTL, Bedrock Converse observability) and Ring (debugging detection from the camera's own stills).

**Out of scope:**
- Switching door detection to an LLM, or any change to how the door check or the analysis decides.
- Retention beyond 7 days, export or download of traces, and search or filtering beyond the date range.
- Traces for assistant (Ask/MCP) Converse calls.
- Step Functions execution history in the app.
- Blurring the debug stills.
- Re-running a trace with different settings ("replay").
