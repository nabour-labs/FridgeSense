# Design

## Context

The door-event state machine (`infra/lib/door-pipeline.ts`) catches Analyze and Save errors into `MarkFailed`, which ends in `Succeed("AnalysisFailed")`. `FindWindow` and `FetchStills` have only the default Lambda service-exception retries that `LambdaInvoke` adds. The one alarm watches `ExecutionsFailed`. The token-refresh Lambda logs JSON lines via `log_event`; with Lambda's default text log format each line is `[ERROR] <time> <request id> {"event": "token_refresh_rejected", ...}`. `GET /api/warnings` is built by `setup_warnings.warnings_body`; the API handler already loads the token store for every request.

## Goals / Non-Goals

**Goals:** every failed or timed-out door-event run emails the alert address; a rejected refresh emails it and the app says to re-link.

**Non-Goals:** per-function Lambda error alarms, alarms for refreshes inside other Lambdas, a re-link flow in the PWA.

## Decisions

- **`Fail` state instead of a custom metric.** `MarkFailed → Fail("AnalysisFailed")` makes those runs count in `ExecutionsFailed`, so the existing alarm covers them with no new metric. The event is still marked `analysis_failed` first. Alternative (custom metric from `mark_failed_task`) needs `cloudwatch:PutMetricData` and another alarm.
- **Retry `States.TaskFailed` twice, 10 s then 20 s** on `FindWindow` and `FetchStills`. Both are re-runnable: find-window only reads Ring history; fetch-stills overwrites the same S3 keys and the same door record. Catch `States.ALL` into the shared `MarkFailed`, which tolerates a missing `door_sk` (it only exists after `FetchStills` succeeds).
- **Separate timed-out alarm** (`metricTimedOut`) rather than a math expression, matching the existing alarm's shape and test.
- **Metric filter with a plain term pattern** `"token_refresh_rejected"`: works with the text log format (a JSON pattern would not, since the line has a prefix) and the event name is unique.
- **Warning from the token store.** The API handler passes the loaded tokens' `link_status` into `warnings_body`; `needs_relink` goes first and does not depend on a discovered camera. The banner shows the message with no link, since re-linking happens in the Ring app.

## Risks / Trade-offs

- Retrying `FetchStills` repeats Rekognition and S3 work (a few cents at most) on a real failure.
- The relink alarm fires once per rejection; later 3-hourly runs skip (`needs relink`) and do not re-alarm. The app warning stays until re-linked.

## Test strategy

- **Infra (vitest, CDK assertions):** state definition for the `Fail` state, retries and catches on `FindWindow`/`FetchStills`; alarms on `ExecutionsTimedOut` and `TokenRefreshRejected`; metric filter on the token-refresh log group. Synth only, no AWS.
- **Backend (pytest, moto):** `mark_failed_task` without `door_sk`; `GET /api/warnings` with the token store set to `needs_relink` (with and without other problems and cameras) and `linked`. Ring calls stubbed with respx.
- **PWA (vitest + Testing Library):** `Warnings` renders the `needs_relink` banner with no link.
