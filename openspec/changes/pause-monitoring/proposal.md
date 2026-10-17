# Proposal

## Why

When the owner cleans the fridge, defrosts it, has it serviced or renovates the kitchen, the door opens again and again and things go in and out that are not real stock changes. Today every one of those openings is downloaded, checked, sent to Nova (paid out of pocket) and applied to the inventory and open/close stats, so the owner ends up with wrong stock, wrong stats and a cost they did not want. The owner needs a way to switch FridgeSense off for a while and back on, without unlinking the camera or changing anything in the Ring app.

## What Changes

- **Pause and resume per camera.** The owner can pause FridgeSense for the linked camera and resume it later. The state is stored per Ring `account_id` and device ID, with the time it last changed. A camera that was never paused is active.
- **New routes.** `GET /api/camera` gains `monitoring: {"paused": <bool>, "since": "<ISO 8601 UTC>" | null}`. `PUT /api/camera/monitoring` with `{"paused": true | false}` changes it and returns the new `monitoring` object. Viewers get 403, as for every other write.
- **Paused openings are ignored.** While the camera is paused, a signed `motion_detected` webhook still gets 200 and is still deduplicated, but no door-event workflow run starts and the event is logged as `motion_paused`. A run that was already started before the pause stops at the stills step with outcome `paused`, before any Ring download, face detection or Nova call. No door event, inventory change, open/close stat or Nova cost is recorded for those openings.
- **Camera tab switch.** The Config "Camera" tab gets a "FridgeSense" switch at the top: "Active" or "Paused since <local date and time>", with a short line saying what pausing does (for cleaning, maintenance or renovation). Owners and users can flip it; viewers see the state without the switch.
- **Reminder banner.** While paused, `GET /api/warnings` lists `monitoring_paused` first, so the banner on the Fridge and Config screens reminds the owner that openings are not being recorded, with a "Resume on Camera tab" link.

Out of scope:
- Pausing on a schedule or resuming automatically after a set time.
- A reason field (cleaning, maintenance, renovation) stored with the pause.
- Changing the MCP or Ask answers while paused (they keep answering from the stored inventory).
- Turning off live view, snapshots, manual item edits or the camera itself in Ring; those keep working while paused.
- Re-analyzing openings that happened while paused.

Hackathon tracks: **Ring** (respecting how the camera is used in a real home), **AWS Builder** (no Step Functions, Ring, Rekognition or Bedrock work, and no cost, for paused openings).

## Capabilities

### New Capabilities

- `fridge-monitoring`: whether FridgeSense is active or paused for a camera, how it is stored, and the routes that read and change it.

### Modified Capabilities

- `ring-webhook-intake`: a motion event for a paused camera is acknowledged and logged but not handed to the motion handler.
- `door-event-detection`: the stills step ends a run with outcome `paused`, before any download, when the camera is paused.
- `camera-info`: `GET /api/camera` includes the monitoring state, and the Camera tab is no longer read-only for every role: it has the pause switch.
- `setup-warnings`: a new `monitoring_paused` warning, listed first. This capability's spec is still in the un-archived `door-auto-calibration` change, so that change should be archived before this one.

## Impact

- Backend: new `fridgesense/monitoring.py` (load and save the state); `webhook.handle_webhook` gets a paused check; `door_events.fetch_stills` gets a paused check; `handlers/api.py` gets `PUT /api/camera/monitoring` and the `monitoring` field on `GET /api/camera`; `setup_warnings.warnings_body` adds the new warning; `handlers/http.py` wires the check into the webhook.
- Data: one new item per camera in the single table, `pk = ACCOUNT#<account_id>`, `sk = MONITORING#<device_id>`. No migration: a missing item means active.
- Infra: the HTTP API Lambda already reads the table for webhook dedupe; the new route goes through the existing `/api/{proxy+}` integration. The state machine is unchanged, since any outcome other than `door_open` already ends the run in `NoAnalysis`.
- PWA: `api/types.ts` and `api/client.ts` (new `setMonitoring`), `screens/Camera.tsx` (switch), `components/Warnings.tsx` (fix link for the new code).
- Cost: one DynamoDB read per motion webhook and per stills step.
