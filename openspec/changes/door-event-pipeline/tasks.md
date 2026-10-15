# Tasks

## 1. Setup and fixtures

- [ ] 1.1 Add `pillow` to backend dependencies and a test helper that makes solid and half-bright JPEGs; verify `uv run pytest` still passes and `uv export --no-dev` lists pillow
- [ ] 1.2 Add fixtures `ring/history_events.json`, `ring/history_events_pending.json`, `ring/history_events_string_ts.json`, `nova/converse_tool_use.json`, `nova/converse_text_then_tool.json`, `nova/converse_end_turn.json`; extend the fixture-parsing test and verify it passes

## 2. Webhook hand-over to Step Functions

- [ ] 2.1 Write failing tests for "Motion event starts a run" and "Same event handed over twice" (Stubber on `stepfunctions`: exact `StartExecution` input and name; `ExecutionAlreadyExists` counts as success); verify they fail
- [ ] 2.2 Implement `StepFunctionsMotionHandler` and run naming, and select it when `STATE_MACHINE_ARN` is set, to make the tests pass
- [ ] 2.3 Write failing webhook tests for "Motion handler fails" and "Ring retries after a failed hand-over"; verify they fail
- [ ] 2.4 Implement forgetting the request ID and answering 500 on hand-over failure to make the tests pass

## 3. Event window

- [ ] 3.1 Write failing tests for "Recording finished", "Timestamps as strings", "Recording not finished yet", "Recording never finishes" (respx on history; `find_window` task with `attempt`); verify they fail
- [ ] 3.2 Implement the `find_window` task to make the tests pass

## 4. Stills and door-open check

- [ ] 4.1 Write failing unit tests for still times and for "Fridge light visible", "Door stayed closed" (brightness part), "Box and threshold from config"; verify they fail
- [ ] 4.2 Implement still timing and the brightness check (`DOOR_BOX`, `DOOR_THRESHOLD`) to make the tests pass
- [ ] 4.3 Write failing tests (respx + moto S3) for "Four stills saved", "Download link gets no token", "Still not ready yet", "Too few stills"; verify they fail
- [ ] 4.4 Implement still download and S3 storage to make the tests pass
- [ ] 4.5 Write failing tests (moto DynamoDB) for "Door event saved", "Same Ring event in two runs", "Door stayed closed" (no door event, `motion_not_door` log), and "Too few stills" (`status = "no_media"`); verify they fail
- [ ] 4.6 Implement the `fetch_stills` task: claim transaction, door event record, and outcomes `door_open`, `not_door`, `no_media`, `duplicate`, to make the tests pass

## 5. Nova analysis

- [ ] 5.1 Write failing Stubber tests for "Request built from stills and inventory", "Empty inventory", "Stills sent as bytes" (exact `converse` request); verify they fail
- [ ] 5.2 Implement request building (labels, images, prompt, forced tool, temperature 0, model from config) to make the tests pass
- [ ] 5.3 Write failing tests for "Valid answer", "Text before the tool call", "Values out of range", "Invalid answer retried once", "Invalid answer twice"; verify they fail
- [ ] 5.4 Implement response parsing, normalization and the one retry on an invalid answer to make the tests pass
- [ ] 5.5 Write failing tests for "Throttled once" (task raises `BedrockRetryable`, then succeeds on the next call) and "Request rejected" (`ValidationException` and `AccessDeniedException` mark the door event `analysis_failed` without raising `BedrockRetryable`); verify they fail
- [ ] 5.6 Implement Bedrock error mapping and the `analyze` and `mark_failed` tasks to make the tests pass
- [ ] 5.7 Write failing tests for "Cost of one analysis" and "Cost of a retried analysis" (`nova_cost` log lines and `nova_usd`); then implement cost calculation and logging, and verify they pass

## 6. Inventory

- [ ] 6.1 Write failing tests (moto) for "New item added", "Existing item added again", "Item removed", "Removing more than is known", "Removing an unknown item"; verify they fail
- [ ] 6.2 Implement name normalization and the quantity updates in the `save` task to make the tests pass
- [ ] 6.3 Write failing tests for "Low-confidence item", "Exactly at the cutoff", "Door event completed", "Save step retried", "Nothing changed"; verify they fail
- [ ] 6.4 Implement pending changes and the conditional transaction (`already_saved`) to make the tests pass
- [ ] 6.5 Write an end-to-end test that runs the tasks in state-machine order (find_window → fetch_stills → analyze → save) for a bright opening and for a closed door, checking the inventory and door event; verify it passes

## 7. Infrastructure

- [ ] 7.1 Write failing Vitest assertions: a state machine with Wait 20 s → FindWindow → Choice loop → FetchStills → Choice → Analyze (Retry on `BedrockRetryable`: 2 retries, 5 s, backoff 2; Catch → MarkFailed) → Save; the pipeline Lambda (arm64, 512 MB, 90 s, env `DOOR_BOX`, `DOOR_THRESHOLD`, `NOVA_MODEL_ID`, `NOVA_PRICE_IN`, `NOVA_PRICE_OUT`, `STILLS_BUCKET`, plus the shared vars); verify they fail
- [ ] 7.2 Write failing Vitest assertions for the stills bucket ("Stills deleted after 7 days": a lifecycle expiration of 7 days; public access blocked; SSL enforced; encrypted) and for IAM (Bedrock `InvokeModel` only on the Nova 2 Lite profile and its three regional model ARNs; the webhook Lambda has `states:StartExecution` only on this state machine and gets `STATE_MACHINE_ARN`); verify they fail
- [ ] 7.3 Implement the bucket, pipeline Lambda, state machine, IAM and CDK context (`doorBox`, `doorThreshold`, `novaModelId`) to make the tests pass; verify `cdk synth` with real bundling includes Pillow's arm64 binaries

## 8. Docs and final check

- [ ] 8.1 Update the README: what happens on a door opening, how to tune `doorBox`/`doorThreshold` from the `motion_not_door` logs, where to find `nova_cost` lines, and the cross-region inference note; verify the commands match the code
- [ ] 8.2 Run `cd backend && uv run pytest && uv run ruff check && uv run ruff format --check` and `cd infra && npm test && npx tsc --noEmit`; all green
