# Design

## Context

Roles are `owner`, `user` and `viewer` (`session.ROLES`). The API's `@route(..., write=True)` flag already refuses viewers with 403 `{"error": "read-only"}`; `owner=True` also refuses `user`. The PWA's `canEdit(role)` is the matching UI check.

## Decisions

- **`write=True`, not `owner=True`, on the live routes.** Setup snapshots (Reference images, Open/close detection, Fridge area) take a live frame first and fall back to Ring's older still when the live view fails. Those screens are open to `user`, so owner-only live view would silently degrade their snapshots. The threat is the demo passcode, which is `viewer`.
- **Mute `httpx` in `logs.py`.** Every handler imports `fridgesense.logs` (directly or through the modules it uses), so muting it there at import covers all Lambdas. `assistant.py` keeps its own mute for `httpx2`, or moves to the shared one.
- **Webhook limit 50 rps, burst 100.** Ring sends a handful of webhooks per door opening. The account-level limit is 10,000 rps, so a higher per-route limit costs nothing. It doesn't stop a determined flood, but it raises the bar from 15 rps to above 50 rps. Unsigned requests are rejected before any AWS call except the Lambda run itself.

## Risks / Trade-offs

- Judges using the demo passcode no longer see the live view. The Activity feed, stills (blurred) and inventory still show the product.
- A higher webhook limit allows more unsigned Lambda runs during a flood. Each one returns 401 within milliseconds, so the cost is small.

## Test strategy

- **Unit (pytest):** `test_api_live.py`: viewer calling POST and DELETE gets 403 and respx shows no Ring call; the existing owner scenarios stay green. `test_logs.py`: after importing each handler module, `logging.getLogger("httpx").level >= WARNING`.
- **Infra (vitest, CDK assertions):** `guards.test.ts`: `RouteSettings["POST /ring/webhook"]` is `{ThrottlingRateLimit: 50, ThrottlingBurstLimit: 100}`, the passcode route entries are unchanged, and the stage depends on the webhook route.
- **PWA (vitest + Testing Library):** `Activity.test.tsx`: owner and user see "Livestream" and the viewer doesn't. `Camera.test.tsx`: the viewer sees no "Check decoder" button.
- Nothing calls live Ring or AWS; respx and CDK synth only.
