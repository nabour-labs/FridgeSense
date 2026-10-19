# Tasks

## 1. Usage route

- [x] 1.1 Write failing tests in `backend/tests/test_api_usage.py` for "Day with calls", "Day without calls", "Another account's totals are not read", "Bad day" and "Not the owner"; run `uv run pytest tests/test_api_usage.py` and see them fail with 404
- [x] 1.2 Implement `GET /api/debug/usage` in `handlers/api.py` until those tests pass

## 2. Debug page card

- [x] 2.1 Write a failing test in `pwa/src/api/client.test.ts` that `debugUsage` requests `/api/debug/usage?day=<YYYY-MM-DD>`; add `UsageTotals` and `debugUsage` until it passes
- [x] 2.2 Write failing tests in `pwa/src/screens/Debug.test.tsx` for "Totals shown", "Picking another day" and "Usage fails to load"; confirm they fail
- [x] 2.3 Add the "LLM usage" card below the day picker in `screens/Debug.tsx` until those tests pass

## 3. Finish

- [x] 3.1 Run the full backend suite (`uv run pytest`, `uv run ruff check`) and PWA suite (`npm test`, `npm run lint` if present) green
