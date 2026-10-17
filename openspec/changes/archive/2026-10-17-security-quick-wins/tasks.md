# Tasks

## 1. Live view refused for viewers

- [x] 1.1 Write failing tests in `backend/tests/test_api_live.py` for "Viewer opens a live view" (now 403), "Viewer refused a close" and "User opens a live view"; update "Live view closed" to a user token. Run them red.
- [x] 1.2 Add `write=True` to both live routes in `handlers/api.py`. Verify 1.1 and all live tests pass.

## 2. PWA hides live view from viewers

- [x] 2.1 Write failing tests: `Activity.test.tsx` "Button for every role" (owner and user see it, viewer doesn't); `Camera.test.tsx` "No Decoder card for a viewer". Run them red.
- [x] 2.2 Gate the Livestream button and the Decoder card on `canEdit(role)`. Verify 2.1 passes.

## 3. httpx never logs URLs

- [x] 3.1 Write failing tests in `backend/tests/test_logs.py` for "Handler muted on import" (subprocess per handler) and "Signed URL fetched during a pipeline run" (respx + caplog). Run them red.
- [x] 3.2 Mute `httpx` in `fridgesense/logs.py` and make sure every handler imports it. Verify 3.1 passes.

## 4. Webhook throttle

- [x] 4.1 Write failing tests in `infra/test/guards.test.ts` for "Webhook route throttled" and "Webhook route exists before its limit". Run them red.
- [x] 4.2 Add the webhook route's limit and the stage dependency in `infra/lib/fridgesense-stack.ts`. Verify 4.1 passes.

## 5. Checks

- [x] 5.1 Run `cd backend && uv run pytest -q && uv run ruff check`, `cd infra && npm test`, `cd pwa && npm test && npx tsc --noEmit -p .` green and report the results.
