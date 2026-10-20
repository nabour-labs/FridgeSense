# Design

## Context

`UsageRecorder` (`fridgesense/usage.py`) already adds each LLM call to `ACCOUNT#<account_id>` / `USAGE#<YYYY-MM-DD>` in the household time zone. This change only reads it.

## Decisions

- **One day, matching the picker.** The Debug page lists one day at a time, so the route takes one `day`. The PWA sends the picked local date; the stored day is the household day (`TIME_ZONE`). For a single-household demo both are the same zone.
- **Input tokens include cached input.** Converse reports `inputTokens` as uncached input only. "Input tokens" on the page means all input the model read, so the route sums uncached, cache read and cache write. Cost already prices each part separately.
- **Owner only**, like the other `/api/debug/*` routes.
- **Card is its own component** with its own load, so a failure there does not hide the motions list.

## Test strategy

- Backend (pytest, moto DynamoDB): `tests/test_api_usage.py` writes `USAGE#` items with `FridgeTable().add_many` and calls the handler through `tests/api_helpers.call`, covering every route scenario including roles.
- PWA (Vitest + Testing Library): `screens/Debug.test.tsx` with the existing fake API, covering the shown totals, the day change and the failure case. `api/client.test.ts` checks the request path.
- No live AWS or Bedrock calls.
