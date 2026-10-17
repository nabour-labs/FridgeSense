## Why

During judging (Nov 9–20) nobody watches the logs, so failures must reach the alert email or the app. Two gaps hide them today:

- A failed Nova analysis or save goes through `MarkFailed` and then a `Succeed` state, so the run counts as succeeded and the only alarm (`ExecutionsFailed`) never fires. Timed-out runs are not alarmed either, and `FindWindow` and `FetchStills` have no retry or catch at all.
- A rejected Ring token refresh sets `link_status = "needs_relink"` and logs `token_refresh_rejected`, but nothing alarms on it and the app shows no warning, so the camera silently stops recording door openings.

Tracks: Ring (keeping the Ring link healthy), AWS Builder (Step Functions, CloudWatch, SNS).

## What Changes

- After `MarkFailed` the door-event run ends in a `Fail` state, so Nova and save failures count as `ExecutionsFailed` and trip the existing alarm.
- `FindWindow` and `FetchStills` retry task failures, then catch any error into `MarkFailed`. `MarkFailed` marks the door event `analysis_failed` when the run already has one, and only logs when it does not.
- A second alarm on `ExecutionsTimedOut` for the door-events state machine, sending to the same SNS topic.
- A CloudWatch metric filter on the token-refresh log group counts `token_refresh_rejected` events, and an alarm on that metric emails the alert topic.
- `GET /api/warnings` lists a `needs_relink` warning first when the Ring account needs re-linking, and the PWA banner shows its message (no fix link, since re-linking happens in the Ring app).

Out of scope: alarms on Lambda errors in other functions, token refresh failures inside pipeline or API calls (the 3-hourly job catches them), automatic re-link, any dashboard.

## Capabilities

### New Capabilities
- `setup-warnings`: problems that stop door openings being recorded, shown by `GET /api/warnings` and the app banner (this change adds the re-link warning).

### Modified Capabilities
- `door-event-detection`: failed runs end as failed executions; window and stills steps retry and mark the event failed.
- `cost-and-abuse-guards`: alarms on timed-out door-event runs and on rejected Ring token refreshes.

## Impact

- `infra/lib/door-pipeline.ts`, `infra/lib/fridgesense-stack.ts`, `infra/test/pipeline.test.ts`, `infra/test/guards.test.ts`
- `backend/src/fridgesense/inventory.py` (`mark_failed_task`), `backend/src/fridgesense/setup_warnings.py`, `backend/src/fridgesense/handlers/api.py`, their tests
- `pwa/src/api/types.ts`, `pwa/src/components/Warnings.tsx` and its test
- No new AWS cost beyond two alarms and one metric filter (~$0.20/month).
