# Design

## Context

`ring-access` is live in code. These pieces exist already:
- **Webhook:** verifies the signature, dedupes by `request_id`, and hands `MotionEvent`s to a pluggable `MotionHandler` (`fridgesense.handlers.http.motion_handler`).
- **`RingClient`:** handles token refresh. The table already holds `ACCOUNT#…/DEVICE#…` and `ACCOUNT#…/WEBHOOK#…` items.

See proposal.md for scope. Ring contract details come from Ring's API documentation, as recorded for `ring-access`:
- The event history lists events newest first, with `attributes.start` and `end` in epoch ms (sometimes as strings).
- Image download answers 303 with a pre-signed `Location`, plus 416/425 while a recording isn't ready.

Nova facts were checked against AWS docs on Oct 14:
- **Model access:** Nova 2 Lite is only reachable through an inference profile in us-east-1 (`us.amazon.nova-2-lite-v1:0`, routed to us-east-1, us-east-2 or us-west-2), and is enabled by default.
- **Images:** up to 5 per request as bytes, billed at a flat 230 tokens per image.
- **Structured output:** Bedrock's `outputConfig` structured output isn't supported for Nova, so JSON comes from a forced tool with constrained decoding, at temperature 0.
- **Prompt layout:** text labels go before each image, and instructions go in the user turn after the images.
- **Price (`us.` profile):** $0.00033 input and $0.00275 output per 1K tokens.

## Goals / Non-Goals

**Goals:**
- A door opening reaches the inventory within about 60–90 s of the door closing.
- Every step is safe to retry, and no Ring event is counted twice.
- Door box, threshold, model and prices are configurable without code changes.

**Non-Goals:**
- Sub-minute latency. Ring needs time to finish the recording, and we wait for it.
- Handling several cameras at once beyond keying by device ID.
- An Express workflow or batching.

## Decisions

### Workflow: Step Functions Standard, one run per motion event
```
Start ─► Wait 20 s ─► FindWindow ─┬─ pending ─► Wait 20 s ─► FindWindow (attempt+1)
                                  └─ ready ──► FetchStills ─┬─ not_door / no_media / duplicate ─► Succeed
                                                            └─ door_open ─► Analyze ─► Save ─► Succeed
                                                                               └─ (error) ─► MarkFailed ─► Succeed
```
- **Run name:** `<device id with non [A-Za-z0-9-_] replaced by '-', last 50 chars>-<timestamp_ms>`. Standard workflows refuse a duplicate name for 90 days, which gives exactly-once starts for free; `ExecutionAlreadyExists` is treated as success.
- **Retry limit:** `FindWindow` gets an `attempt` counter. On attempt 6 it returns the fallback window (timestamp + 30 s) instead of pending, so the loop always ends.
- **Retries on Analyze:** `Analyze` raises `BedrockRetryable` for throttling, timeouts and 5xx. The state machine retries it twice (3 attempts), 5 s apart with backoff 2. A `Catch` on `States.ALL` goes to `MarkFailed`.
- *Alternative:* SQS with delayed messages. That needs more custom retry and wait code and gives no visual workflow for the AWS Builder judges.
- *Alternative:* an Express workflow. It's cheaper per transition, but has no name dedupe. At about 10 transitions per opening, Standard costs about $0.00025 per opening.

### One pipeline Lambda, task chosen by input
- `fridgesense.handlers.pipeline.handler` dispatches on `event["task"]`: `find_window`, `fetch_stills`, `analyze`, `save` or `mark_failed`. The state machine passes the task name in each `LambdaInvoke` payload.
- It runs on arm64 with 512 MB (Pillow) and a 90 s timeout.
- *Alternative:* one function per step. That's five log groups and five IAM roles for the same code.

### Starting runs from the webhook
- `StepFunctionsMotionHandler` replaces `LoggingMotionHandler` when `STATE_MACHINE_ARN` is set.
- **Hand-over failure:** if `motion.handle` raises, the webhook deletes its `WEBHOOK#<request_id>` record and answers 500, so Ring retries. That retry is safe because of the run-name dedupe.

### Stills and the door-open check
- **Still times:** 4 stills at 1/5, 2/5, 3/5 and 4/5 of the window.
- **Retries:** each still is tried up to 3 times, with 3 s, then 6 s, between attempts on 416/425. A 403 counts as missing.
- **Download:** the `Location` URL is fetched with a plain `httpx` GET, without the Ring client, so no token leaves for another host.
- **Storage:** stills are stored with `ContentType: image/jpeg`.
- **Brightness:** Pillow converts to grayscale (`L`), crops the box `DOOR_BOX="x,y,w,h"` (fractions, default `0.25,0.1,0.5,0.8`), and takes `ImageStat.Mean / 255`.
- **Threshold:** the door counts as open if the brightest still is at or above `DOOR_THRESHOLD` (default `0.5`).
- **Config:** both values come from CDK context (`doorBox`, `doorThreshold`) and become Lambda env vars. On Oct 21, tuning them is a `cdk.json` edit plus a deploy.

### Data model additions (single table)

| Item | pk | sk | Attributes |
| --- | --- | --- | --- |
| Door event | `ACCOUNT#<acct>` | `DOOR#<opened_at ISO>#<device_id>` | `device_id`, `ring_event_id`, `opened_at`, `closed_at`, `duration_s`, `still_keys`, `status` (`analyzing` / `done` / `analysis_failed` / `no_media`), `changes`, `pending_count`, `nova_usd` |
| Ring event claim | `ACCOUNT#<acct>` | `RINGEVENT#<device_id>#<ring_event_id>` | `door_sk` |
| Inventory item | `ACCOUNT#<acct>` | `ITEM#<normalized name>` | `name`, `category`, `quantity`, `first_seen_at`, `last_changed_at` |
| Pending change | `ACCOUNT#<acct>` | `PENDING#<opened_at ISO>#<n>` | `door_sk`, `item`, `category`, `direction`, `quantity`, `confidence` |

- **Claiming a door event:** one `TransactWriteItems` puts the claim (`attribute_not_exists(sk)`) and the door event together. A cancelled transaction caused by the claim means `duplicate`. The fallback window has no Ring event ID, so it uses `ts-<timestamp_ms>` instead.
- **Save:**
  1. Read the current items.
  2. Compute the new quantities, floored at 0.
  3. Write one transaction: update the door event (`status = analyzing` as the condition), and put each inventory item and each pending change.
  - If the door event's condition fails, the result is `already_saved`.
  - The transaction holds at most about 40 items; Nova will not list 100 changes for one opening.
- No new indexes: the PWA and the MCP server query `begins_with(sk, "ITEM#")` and `begins_with(sk, "DOOR#")` within the one account.

### Analysis request
- **Model:** `NOVA_MODEL_ID`, default `us.amazon.nova-2-lite-v1:0`.
- **Settings:** `inferenceConfig = {"maxTokens": 1024, "temperature": 0}`.
- **Tool schema:** the tool is `record_fridge_changes`, with this input schema:
  - Top level: an object with `added` and `removed` arrays.
  - Each array entry: an object with `item` (string), `category` (enum), `quantity` (integer) and `confidence` (number).
  - The category enum is `dairy`, `produce`, `meat`, `seafood`, `beverage`, `snack`, `condiment`, `leftovers`, `bakery`, `frozen`, `other`.
  - That's two levels of nesting, as Nova recommends.
- **Prompt:**
  - It asks for item types rather than brands, and for counts of whole items.
  - It tells Nova to report nothing when nothing changed, and that a confidence below 0.7 means "unsure".
  - It includes the current inventory names, which helps Nova reuse existing names ("milk", not "milk jug").
- **Validation:** a Pydantic model checks the tool input after normalization (category fallback, quantity at least 1, confidence clamped).
- **Invalid answers:** up to 2 requests per attempt.
- **Cost:** `usd = in/1000 × NOVA_PRICE_IN + out/1000 × NOVA_PRICE_OUT`, rounded to 6 decimals per call, then summed.
- **Bedrock client:** `botocore.config.Config(retries={"max_attempts": 1}, read_timeout=60)`. Retries belong to the state machine, so they're visible and bounded.

### Infrastructure
- **Bucket:** `fridgesense-stills-<account>`, with public access blocked, SSL enforced and S3-managed encryption.
  - A lifecycle rule expires objects after 7 days.
  - `RemovalPolicy.DESTROY` with `autoDeleteObjects`, so a destroy really deletes the stills.
- **Pipeline Lambda IAM:**
  - Read and write on the bucket and the table, plus read on the token and app secrets. Write on the token secret, since a refresh can rotate tokens.
  - `bedrock:InvokeModel` on the inference profile ARN and on the `amazon.nova-2-lite-v1:0` foundation-model ARNs in us-east-1, us-east-2 and us-west-2 only.
- **Webhook Lambda:** gets `states:StartExecution` on the state machine only, and `STATE_MACHINE_ARN` in its env.
- **State machine:** defined in CDK (`aws-stepfunctions` + `LambdaInvoke`), with logging at level ERROR.

## Test strategy

| Level | What | How |
| --- | --- | --- |
| Unit (pytest) | Window matching, still times, brightness box and threshold, name normalization, analysis normalization, cost math, run naming | Pure functions; test images generated with Pillow (solid or half-bright JPEGs), no binary fixtures |
| Contract (pytest + respx) | Ring history and image download (303 → `Location` → GET without auth, 416/425/403) | respx; history fixtures with number and string timestamps |
| Contract (pytest + Stubber) | Bedrock Converse request shape and responses (valid, text-then-tool, `end_turn`, out-of-range values, `ThrottlingException`, `ValidationException`) | `botocore.stub.Stubber` on a real `bedrock-runtime` client; asserts the exact request dict |
| Integration (pytest + moto) | Each pipeline task against moto DynamoDB and S3; webhook to `StartExecution` and the failure path; a full run calling the tasks in state-machine order for a door opening and for a closed door | moto `mock_aws`; Ring through respx; Bedrock through Stubber. Step Functions `StartExecution` through Stubber, because moto does not reject duplicate run names |
| Infra (Vitest) | State machine definition (states, wait times, retry and catch on Analyze), bucket lifecycle and encryption, Bedrock IAM scoped to the Nova profile and models, webhook can only start this state machine, pipeline env vars | `Template.fromStack` |

New fixtures go in `backend/tests/fixtures/`:
- `ring/history_events.json`
- `ring/history_events_pending.json`
- `ring/history_events_string_ts.json`
- `nova/converse_tool_use.json`
- `nova/converse_text_then_tool.json`
- `nova/converse_end_turn.json`

Nothing calls Ring, AWS or Bedrock.

## Risks / Trade-offs

- [Ring's recording is shorter than a fridge visit] → The stills still cover whatever was recorded. Live sessions to force recording stay out of scope; check the first real openings on Oct 21.
- [The default door box is wrong for the real camera angle] → Each `motion_not_door` log line includes the brightest value, so a few real openings show the right threshold. Box and threshold are deploy-time config.
- [Nova confidence isn't calibrated] → The 0.7 cutoff is a starting point; pending items are confirmed in the PWA. Record the hit rate on 10 test openings for the write-up.
- [Nova 2 Lite end of life "no sooner than Dec 2 2026"] → The model ID is config; Nova Lite v1 (`amazon.nova-lite-v1:0`, about 5× cheaper) is the fallback, needing only a different ID and prices plus an IAM ARN change.
- [Cross-region inference sends stills to us-east-2 or us-west-2] → Still US-only and AWS-internal; noted in the README.
- [Concurrent openings change the same item] → One user, with seconds between openings; the transaction is per door event. Last write wins in the rare case. Accepted.

## Migration Plan

1. `cdk deploy` (with Jayson's approval). It adds the bucket, the state machine and the pipeline Lambda, and updates the webhook Lambda.
2. No data migration: the new item types live alongside the existing ones.
3. Rollback: redeploy the previous commit. Without `STATE_MACHINE_ARN`, the webhook falls back to the logging handler.
