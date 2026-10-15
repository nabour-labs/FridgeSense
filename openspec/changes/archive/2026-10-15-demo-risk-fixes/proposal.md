# Proposal

## Why

A code review found five defects that can break or visibly glitch the live demo: API errors reach the app as HTML, a failed save leaves an opening stuck at "analyzing", the Ask screen keeps listening after you leave it, Activity stills flash and re-download every 10 s, and an in-flight poll can undo a save the user just made. All five are small fixes and should land before the Oct 23 submission.

Tracks: AWS Builder (CloudFront, Step Functions, Bedrock) and Alexa+/Ring indirectly, since the demo shows the whole flow.

## What Changes

- CloudFront no longer turns 403/404 responses into `200 + index.html`. The app uses hash routing, so it never needs a path fallback. `/api/*` errors (`403 read-only`, `404`) reach the app unchanged.
- Door pipeline: if the Save step fails, the door event is marked `analysis_failed` instead of staying `analyzing`. Each Bedrock call gets one HTTP attempt with a read timeout, so two Nova attempts fit inside the pipeline Lambda's timeout. A client-side read or connect timeout counts as a retryable Bedrock error.
- Ask screen: leaving the screen stops speech recognition and any answer being read aloud, and sends no question.
- Activity screen: an event's stills keep the same links across polls while those links are still fresh (under 10 minutes old), so images don't reload or flash.
- Polling screens: a poll response from a request that started before a local change, or before a newer poll, is ignored.

Out of scope (separate follow-ups): API throttling and a budget alarm, running the door check before face detection, Ring token takeover on `/ring/token`, the lost Nova cost when an invalid answer is followed by an error, and moving tuned settings into `cdk.json`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `inventory-api`: API error statuses reach the app unchanged through the CDN.
- `door-event-detection`: a door event never stays `analyzing` after its workflow run ends.
- `fridge-change-analysis`: a Bedrock call has a bounded duration, and a client-side timeout is retryable.
- `inventory-app`: the Ask screen stops on leave, Activity stills keep stable links, and stale poll responses are ignored.

## Impact

- `infra/lib/app-site.ts`, `infra/lib/door-pipeline.ts` and their tests.
- `backend/src/fridgesense/handlers/pipeline.py`, `backend/src/fridgesense/analysis.py` and their tests.
- `pwa/src/useLoad.ts`, `pwa/src/screens/Ask.tsx`, `pwa/src/screens/Activity.tsx` and their tests.
- Needs a `cdk deploy` to take effect. No data migration.
