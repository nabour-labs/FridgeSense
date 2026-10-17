# Design

## Context

Door openings flow webhook → `StepFunctionsMotionHandler.start_execution` → `find_window` (Ring history) → `fetch_stills` (Ring media, door check, face detection, `DOOR#` item) → `analyze` (Nova) → `save` (inventory). In the state machine, any `fetch_stills` outcome other than `door_open` already goes to `NoAnalysis`. The HTTP Lambda that receives webhooks already has read/write access to the single table (`table.grantReadWriteData(httpFn)`) for dedupe. The PWA Camera tab ([pwa/src/screens/Camera.tsx](../../../pwa/src/screens/Camera.tsx)) is read-only today and loads `GET /api/camera` every 60 s; the `Warnings` banner renders on the Fridge and Config screens.

## Goals / Non-Goals

**Goals:**
- Stop all paid work (Step Functions, Ring media, Rekognition, Nova) for openings while paused, with the cheapest possible check.
- Never send Ring a 4xx because of the pause.

**Non-Goals:**
- Cancelling Step Functions runs that are already past the stills step when the owner pauses. They finish; at most one opening slips through.

## Decisions

1. **One small module, `fridgesense/monitoring.py`.** `load(table, account_id, device_id) -> Monitoring` and `set_paused(table, account_id, device_id, paused, now_ms) -> Monitoring`, with `Monitoring(paused: bool, since: str | None)` and `to_body()`. Item: `pk = ACCOUNT#<account_id>`, `sk = MONITORING#<device_id>`, fields `paused`, `since`. `set_paused` reads first and keeps `since` when the state is unchanged. Same shape as `fridge_area.load`/`save`. *Alternative:* a field on the device item from discovery — rejected, because rediscovery rewrites that item.

2. **Two gates, both reading the same item.**
   - *Webhook:* `handle_webhook` takes an optional `paused: Callable[[str, str], bool]`, called after dedupe and after the `MotionEvent` is parsed, before `motion.handle`. `handlers/http.py` passes `lambda a, d: monitoring.load(FridgeTable(), a, d).paused`. An exception from it is logged (`monitoring_check_failed`) and treated as active, so the fetch_stills gate is the backstop and Ring never sees an error caused by the pause.
   - *fetch_stills:* a first check, before any Ring call, returns `{**state, "outcome": "paused"}`. It gets a `paused_for` callable like the existing `setup_for`, wired in `handlers/pipeline.py`. This covers runs started before the pause (each run waits ≥ 20 s before this step, which is when someone pausing on the spot opens the door).
   *Alternative:* gate only in `fetch_stills` — simpler, but every paused opening would still start a run and call Ring's history API. *Alternative:* gate in `analyze` — too late, Ring media and Rekognition are already paid for.

3. **Route `PUT /api/camera/monitoring`** with `@route(..., write=True)` and `@with_device` in `handlers/api.py`; body validation is `isinstance(body.get("paused"), bool)`. `GET /api/camera` adds `monitoring` from `monitoring.load` next to the Ring body, so it is present when Ring is unavailable. No infra change: `/api/{proxy+}` already routes it.

4. **Warning first in the list.** `setup_warnings.warnings_body` inserts `monitoring_paused` before `motion_detection_off`. It is a table read, not a Ring call, so it is present when Ring is down.

5. **PWA.** `CameraInfo.monitoring` and `api.setMonitoring(paused)` in the client. A `Monitoring` card at the top of `Camera.tsx` uses a `role="switch"` button with `aria-checked`, shown when `canEdit(role)`. While the request is in flight the switch is disabled. On success it shows the returned state; on failure it reverts and shows the error line. `Warnings.fixes` gets the `monitoring_paused` case → `{label: "Resume on Camera tab", href: "#config"}`, and `SetupWarning` gets the new variant.

## Risks / Trade-offs

- [Owner forgets to resume] → banner on the Fridge and Config screens on every visit while paused.
- [A run already past fetch_stills when paused] → it finishes and that one opening is analyzed. Accepted.
- [Extra DynamoDB read per motion webhook] → one GetItem, a few ms, well within the 5 s budget.
- [The `setup-warnings` spec lives in the un-archived `door-auto-calibration` change] → archive that change before this one, so this ADDED requirement lands on an existing spec.

## Migration Plan

No data migration: a missing item means active. Deploy backend and PWA together with `cdk deploy` (with Jayson's OK). Rollback: redeploy the previous version; leftover `MONITORING#` items are ignored.

## Test strategy

- **Unit (pytest, moto DynamoDB):** `monitoring.load`/`set_paused` (never paused, per account/device, `since` kept when unchanged).
- **Unit (pytest):** `handle_webhook` with the recorded `tests/fixtures/ring/` motion webhook, a fake motion handler and a fake `paused` callable (paused, duplicate while paused, active, raising, status event while paused).
- **Unit (pytest):** `fetch_stills` with `paused_for` returning true: assert outcome `paused` and that the stub Ring client, HTTP client, blurrer and table saw no calls. Existing `test_fetch_stills_task.py` helpers.
- **Contract (pytest, `api_helpers.py`):** `GET /api/camera` `monitoring` with Ring stubbed OK and 500; `PUT /api/camera/monitoring` for owner, user, viewer, no token, no camera, bad bodies, idempotent repeat; `GET /api/warnings` order.
- **Component (Vitest + Testing Library):** Camera tab switch (active, pause, resume, failure revert, viewer) with a fake `api`; Warnings banner link for `monitoring_paused`.
- **Infra:** none; the route goes through the existing proxy.
- Nothing calls live Ring, AWS or Bedrock.
