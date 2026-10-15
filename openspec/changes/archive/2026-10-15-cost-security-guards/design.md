# Design

## Context

- `infra/lib/fridgesense-stack.ts` creates `new HttpApi(this, "Api", ...)` with the default `$default` stage and no throttling. The four Ring routes are added there; `AppSite` adds `ANY /api/{proxy+}` (which today also serves `POST /api/session`), and `McpEndpoint` adds the MCP route. CloudFront forwards `/api/*` to the same API.
- The stack has no budget, no SNS topic and no alarm. The state machine is `fridgesense-door-events` in `DoorPipeline` (`doors.stateMachine`).
- `door_events.download_stills` downloads each still, calls `FaceBlurrer.blur` (Rekognition `DetectFaces`) and `s3.put_object` per still, and returns `(key, blurred bytes)`. `fetch_stills` then runs `DoorCheck.evaluate` on the blurred bytes. Most webhook events are motion with the door shut, so each pays up to 4 DetectFaces calls and 4 S3 PUTs for nothing.
- `linking.token_exchange` always `store.save(...)`s the new grant as `unclaimed`. `RingClient` uses whatever is in the store regardless of `link_status`, so the overwrite takes effect for the pipeline immediately.

## Goals / Non-Goals

**Goals:**
- Cap request rates on the public API, with tight limits on the two passcode checks.
- Email the owner at 80% of a $20 monthly budget and on any failed door-event execution.
- No face detection or storage for motion that is not a door opening.
- `POST /ring/token` can no longer swap a different Ring account into a linked install.

**Non-Goals:**
- WAF, per-IP limits, budget actions, per-service budgets.
- A pending-grant store (see Decisions).

## Decisions

### 1. Throttling through the L1 stage
`HttpApi`'s default stage exposes no route-level throttle props, so the stack sets them on the `$default` stage's `CfnStage` (`api.defaultStage.node.defaultChild`):
- `defaultRouteSettings = { throttlingRateLimit: 10, throttlingBurstLimit: 20 }`
- `routeSettings = { "POST /api/session": {1, 3}, "POST /ring/link": {1, 3} }`

API Gateway rejects route settings for a route key that does not exist yet ("Unable to find Route by key"), and CloudFormation does not infer that dependency, so the stage `addDependency`s both route constructs. `AppSite` adds an explicit `POST /api/session` route on the existing app API integration and exposes it so the stack can reference it; the backend already dispatches on `(method, path)`, so nothing changes in `api.py`.

Limits are per route across all callers, not per client: during an attack the real user also sees 429 on sign-in. Acceptable for a demo; the 32-character generated passcode is the real defence, the limit mainly protects the optional short `demo_passcode`.

Ring webhooks (a few per door opening) are far below 10/s, so the throttle will not produce the 4xx streak that disables a webhook.

### 2. Budget and alarm
- `CfnBudget` (`aws-cdk-lib/aws-budgets`): `COST`, `MONTHLY`, 20 USD, one `ACTUAL` / `GREATER_THAN` / 80 `PERCENTAGE` notification with an `EMAIL` subscriber. Account-wide (no cost filters): the account is used for this project.
- `Topic` + `EmailSubscription(alertEmail)`; `Alarm` on `doors.stateMachine.metricFailed({ period: 5 min, statistic: Sum })`, threshold 1, `GREATER_THAN_OR_EQUAL_TO_THRESHOLD`, 1 evaluation period, `NOT_BREACHING`, with an `SnsAction`.
- `alertEmail` comes from `this.node.tryGetContext("alertEmail")`; empty or missing throws `Error("Set the alert email: cdk deploy -c alertEmail=you@example.com")`. Failing loudly beats silently deploying without a cost guard. `infra/test/helpers.ts` passes `alertEmail: "owner@example.test"` by default so existing tests keep synthesizing; the missing-address test overrides it with `""`. Jayson supplies the real address at deploy time (`-c alertEmail=...`); it can also live in his local, untracked `cdk.context.json`, which is gitignored if not already — check and add it to `.gitignore` if needed.
- Read-only `cdk synth` / `cdk diff` also need the context value from now on; the README deploy command gets `-c alertEmail=...`.

### 3. Door check before blurring
Split `download_stills` into:
- `download_stills(ring, http, state, sleep) -> list[tuple[int, bytes]]` — still number and raw bytes, in memory only.
- `store_blurred_stills(s3, bucket, blurrer, state, raw) -> list[tuple[str, bytes]]` — blur each, drop on detection failure (unchanged fail-closed rule), `put_object` the blurred bytes.

`fetch_stills` becomes: download → if fewer than `MIN_STILLS` raw, `no_media` → `check.evaluate(raw bytes)` → not open: `not_door` (nothing stored, no DetectFaces) → open: `store_blurred_stills`; if fewer than `MIN_STILLS` blurred survive, `no_media`, else `analyzing`. The analysis step already reads stills back from S3 by `still_keys`, so Nova still only sees blurred bytes.

Brightness on the raw still versus the blurred still differs only inside face boxes; the fridge-light box is dominated by the lit interior, so the threshold needs no change.

### 4. Refuse to replace a different linked account
In `token_exchange`, after the code exchange and `users_me`, load the store; if it holds tokens with `link_status in {"linked", "needs_relink"}` and a different `account_id`, log `token_exchange_refused` (warning, `account_id` = stored, `new_account_id` = incoming) and return 409 `{"error": "another account is linked"}` without saving. Otherwise save as today.

Alternative considered: store new grants as `pending` and promote in `link_submit` after the passcode + nonce check. It also covers the `unclaimed` window but needs a second token slot, a `RingClient` bound to the pending tokens for the app-integrations calls, and changes to token refresh. Too much surface for the deadline. The remaining gap (an attacker racing the very first link) is small for a single-user demo. To switch Ring accounts on purpose, Jayson resets the `fridgesense/ring-tokens` secret to `{}`.

The 409 goes to Ring's token-exchange call, not the webhook, so it does not count toward webhook disabling.

## Risks / Trade-offs

- [Throttle hits the real user during an attack] → limits are per route; only sign-in and the link page are tight.
- [Stage route settings deploy order] → explicit stage dependency on the two routes, asserted in a test.
- [Email subscription unconfirmed] → SNS sends a confirmation email on first deploy; the alarm emails nothing until Jayson clicks it. Noted in the deploy summary.
- [Budget is account-wide] → any other spend in the account counts; fine for a dedicated account.
- [Refusal rule leaves the unclaimed window open] → accepted; see Decision 4.
- Existing tests `test_door_check_runs_on_blurred_stills` and `test_door_check_uses_the_blurred_bytes_not_the_download` encode the old requirement. They are replaced by tests for the modified scenarios, as the spec change allows; this is not weakening a test.

## Test strategy

- **Unit (pytest, moto for S3/DynamoDB/Secrets Manager, stub `FaceBlurrer`/Rekognition Stubber as in existing tests, `httpx.MockTransport` for Ring with JPEG fixtures from the existing helpers):**
  - `tests/test_stills.py` — raw download returns bytes and writes nothing; `store_blurred_stills` writes only blurred bytes.
  - `tests/test_fetch_stills_task.py` — closed door makes zero DetectFaces calls and zero S3 objects; open door blurs and stores; too few raw stills → `no_media` with no DetectFaces; too few survive blur → `no_media`; door check on downloaded bytes with a face in the box.
  - `tests/test_token_exchange.py` — the four new scenarios (different linked, different needs_relink, same account, different while unclaimed) plus existing ones.
- **Contract (CDK `Template` assertions, `infra/test/stack.test.ts` or a new `guards.test.ts`):** stage default and route settings, `POST /api/session` route and integration, stage `DependsOn`, budget properties, alarm metric/threshold/action, SNS email subscription, missing `alertEmail` throws.
- **Integration:** `tests/test_pipeline_e2e.py` keeps passing with the reordered fetch step. No live AWS, Ring or Bedrock calls.
