# Proposal

## Why

`ring-access` gets motion webhooks from the fridge camera into the backend, but nothing happens with them yet. This change is the core of the demo: a door opening turns into a list of what went in or came out, and the running inventory updates within about a minute. Every front end (PWA, MCP server) reads what this pipeline writes. Analysis uses stills rather than video because the plan cut ffmpeg and container Lambdas, and stills are sharper anyway.

Tracks: **Ring** (motion events, event history and image download through Ring APIs at runtime) and **AWS Builder** (Step Functions, Bedrock Nova, DynamoDB, S3).

## What Changes

- The webhook's motion handler stops only logging and starts one Step Functions execution per motion event, named after the event so a repeat can't start a second run.
- A Step Functions workflow:
  1. Wait until Ring has finished the recording.
  2. Find the event's start and end in Ring's event history.
  3. Download 4 stills spread across the event.
  4. Check whether the fridge door was open, using brightness in a configurable box.
  5. If it was open, ask Bedrock Nova what was added and removed.
  6. Save the door event, the analysis and the inventory changes.
- Stills are stored in S3 under the account and device, and deleted automatically after 7 days.
- Nova's answer is checked against a JSON schema. Changes with confidence of 0.7 or more update the inventory right away; lower ones are saved as pending for the user to confirm in the PWA (`inventory-pwa`).
- Each analysis logs Nova's token usage and its cost in USD.
- The CDK stack gains the state machine, the pipeline Lambdas, the stills bucket and Bedrock permissions for the chosen Nova model only.

## Capabilities

### New Capabilities

- `door-event-detection`: turning a Ring motion event into a door event: event window, stills, door-open check, and a stored open/close record.
- `fridge-change-analysis`: asking Nova what changed in one door opening, validating the answer, and logging its cost.
- `fridge-inventory`: the running inventory, updated from analyses, with low-confidence changes kept pending.

### Modified Capabilities

- `ring-webhook-intake`: adds one requirement. If handing a motion event to the workflow fails, the webhook forgets the request ID and answers 500, so Ring's retry isn't dropped as a duplicate. The existing requirements are unchanged.

## Out of scope

- Video clips, ffmpeg, and live video sessions to force recording.
- Reference photos of the user's own items.
- Confirming pending items, and any UI (`inventory-pwa`).
- Expiry dates, brands, and nutrition.
- Contact sensors.
- Calibrating the door box on real footage. Its defaults are a guess until the camera arrives; it's tuned on Oct 21 by changing config, not code.

## Impact

- Backend: new modules for the workflow tasks, Pillow as a new dependency, and the Bedrock runtime from boto3.
- Infra: a Step Functions state machine, one Lambda for the workflow tasks, an S3 bucket with a 7-day lifecycle, and IAM limited to the one Nova model and the bucket. The webhook Lambda gets `states:StartExecution` on the state machine.
- Cost per door opening: one Nova call on 4 stills (priced in design.md), plus a handful of Lambda and Step Functions transitions. Motion that isn't a door opening costs no Nova call.
- Needs Bedrock access to the Nova model in us-east-1 (a manual console step if not already on).
