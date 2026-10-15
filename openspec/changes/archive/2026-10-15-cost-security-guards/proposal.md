# Proposal

## Why

The Oct 15 codebase review left four cost and security gaps after the demo-risk fixes. AWS costs come out of pocket, and the stack has no spending alert, no failure alarm and no request throttling, so a runaway loop or a script hammering the public API would only show up on the bill. Every motion event (not just door openings) pays for Rekognition face detection and writes stills to S3 before the door check throws most of them away. And `POST /ring/token`, which has no auth by design, overwrites the active Ring tokens before anyone types the passcode, so anyone who can produce a valid code for our app can swap a different Ring account into a linked install.

## What Changes

- **API throttling.** The HTTP API's default stage gets a default route limit (10 requests/s, burst 20). `POST /api/session` and `POST /ring/link`, the two passcode checks, get much lower limits (1 request/s, burst 3) to slow brute force. `POST /api/session` gets its own route so it can carry its own limit; it still goes to the app API function.
- **Budget and alarm.** A monthly cost budget of $20 USD emails an alert when actual spend reaches 80%. A CloudWatch alarm fires when the `fridgesense-door-events` state machine reports any failed execution, and emails the same address through an SNS topic. The address comes from deploy-time context (`-c alertEmail=...`) and is never in the repo; synth fails with a clear message if it is missing.
- **Door check before face detection.** Stills are downloaded into memory, and the brightness door check runs on those raw bytes first. Only if the door was open are the stills sent to face detection, blurred and stored. Motion that is not a door opening makes no face-detection call and stores nothing. The rule "an unblurred still is never stored" and "Nova only sees blurred stills" stay.
- **Ring token takeover guard.** `POST /ring/token` refuses to replace stored tokens that are `linked` (or `needs_relink`) for a different Ring account: it answers 409, logs `token_exchange_refused`, and leaves the store untouched. A new grant for the same account, or any grant when nothing is linked yet, is stored as before.

Hackathon tracks: **AWS Builder** (API Gateway throttling, AWS Budgets, CloudWatch alarm, cheaper Step Functions path) and **Ring** (safer one-way account linking, fewer Ring-derived images stored).

### Out of scope

- Per-client (per-IP) rate limiting or AWS WAF. API Gateway's limits are per route across all callers, which is enough to slow brute force for a single-user demo.
- A pending-grant store with promotion in `link_submit`. The simpler "refuse to replace a different linked account" rule closes the takeover; switching Ring accounts is done by clearing the tokens secret by hand.
- Budget actions that stop resources, cost-allocation tags, or per-service budgets. The budget is account-wide.
- Alarms on Lambda errors, Bedrock spend or DynamoDB throttling.
- Throttling the MCP endpoint differently from the default.

## Capabilities

### New Capabilities

- `cost-and-abuse-guards`: deploy-time guards on the AWS stack: API request limits, the monthly cost budget alert and the failed-execution alarm.

### Modified Capabilities

- `door-event-detection`: stills are door-checked in memory before face detection; only door openings are blurred and stored. "Stills across the opening" and "Door-open check before any analysis" change, and "Only blurred stills are checked and analyzed" is replaced by "Only blurred stills are analyzed".
- `ring-account-link`: token exchange refuses to replace a linked account with a different one.

## Impact

- **Code:** `backend/src/fridgesense/door_events.py` (`download_stills`, `fetch_stills`), `backend/src/fridgesense/linking.py` (`token_exchange`).
- **Infra:** `infra/lib/fridgesense-stack.ts` (stage throttling, budget, SNS topic, alarm, `alertEmail` context), `infra/lib/app-site.ts` (dedicated `POST /api/session` route), `infra/test/helpers.ts` (test `alertEmail`).
- **Deploy:** `cdk deploy` now needs `-c alertEmail=<address>`; the SNS email subscription must be confirmed from the inbox once.
- **API:** callers over the limits get 429 from API Gateway. Ring's webhook (a few calls per door opening) stays far below 10/s.
