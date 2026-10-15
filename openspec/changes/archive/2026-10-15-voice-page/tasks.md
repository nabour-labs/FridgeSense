# Tasks

## 1. Intent matching (fridge-ask)

- [x] 1.1 Write failing tests in `tests/test_ask_parse.py` for "Activity wins over find", "Last opening wins over activity", "Case and punctuation ignored" and "Nothing matches"; run `uv run pytest tests/test_ask_parse.py` and verify they fail because `fridgesense.ask` doesn't exist
- [x] 1.2 Implement `normalize()`, the `Intent` model and the ordered `parse()` skeleton in `fridgesense/ask.py` to make 1.1 pass; verify with the same command
- [x] 1.3 Write failing tests for "Last opened", "Today" and "This week"; then add the last-opening and activity rules and verify they pass
- [x] 1.4 Write failing tests for "Do I have milk", "How many", "Multi-word item" and "Lead-in with no item"; then add item extraction (lead-ins, articles, trailing filler) and verify they pass
- [x] 1.5 Write failing tests for "Whole fridge", "Category in a what question" and "Category asked as an item"; then add the inventory rule, category names, aliases and plurals, and verify they pass
- [x] 1.6 Refactor the rule lists into module-level tables with `tests/test_ask_parse.py` green, and run `uv run ruff check src tests`

## 2. Spoken sentences (fridge-ask)

- [x] 2.1 Write failing tests in `tests/test_ask_say.py` for "Plural names" and "Time phrases"; then implement `plural()` and `ago()` and verify they pass
- [x] 2.2 Write failing tests for "One match", "Several matches", "Ran out" and "Never seen", using hand-built `FindItemResult` objects; then implement `say_find()` and verify they pass
- [x] 2.3 Write failing tests for "Short inventory", "Long inventory" and "Empty category"; then implement `say_inventory()` and verify they pass
- [x] 2.4 Write failing tests for "Openings today" and "No openings this week"; then implement `say_activity()` and verify they pass
- [x] 2.5 Write failing tests for "Milk just went in", "Unsure change" and "Never opened"; then implement `say_last_opened()` and verify they pass
- [x] 2.6 Write failing tests for `ask()` dispatch, including "Hint", where a stub table's `query` must not be called; then implement `ask(table, account_id, question, now, tz) -> AskResult` and verify `uv run pytest tests/test_ask_parse.py tests/test_ask_say.py` passes

## 3. API route (inventory-api)

- [x] 3.1 Write failing moto tests in `tests/test_api_ask.py` for "Do I have milk", "Viewer can ask", "Unknown question" and the API's "No token", through `api.handler` with `link_account()` and `sign_in()`; verify they fail with 404
- [x] 3.2 Add `@route("POST", "/api/ask")` in `handlers/api.py`, calling `ask.ask()` with the household time zone from `TIME_ZONE`, to make 3.1 pass
- [x] 3.3 Write failing tests for "Missing question" and "Too long"; then add body validation (400 `{"error": "question required"}`, no table reads) and verify they pass
- [x] 3.4 Write a failing test for "Activity in the household time zone" (TIME_ZONE America/Toronto, `api.now` at 01:00 local, a door event at 23:30 the day before); make it pass and verify `uv run pytest tests/test_api_ask.py` is green

## 4. Infra: time zone for the API Lambda

- [x] 4.1 Write failing assertions in `infra/test/site.test.ts`: the API function's env has `TIME_ZONE` `America/Toronto` by default, and `America/Vancouver` with `-c timeZone=America/Vancouver`. Run `npm test` in `infra/` and verify they fail
- [x] 4.2 Add a `timeZone` prop to `AppSite`, set from the stack's `context("timeZone", "America/Toronto")`, to make 4.1 pass; verify `npm test` and `npx cdk synth` succeed in `infra/`

## 5. PWA Ask screen (inventory-app)

- [x] 5.1 Write a failing test in `api/client.test.ts`: `ask("do I have milk?")` posts `{"question": "do I have milk?"}` to `/api/ask` with the bearer token. Then add `AskResult` to `types.ts`, `ask()` to `ApiClient`, `"ask"` to the `Api` type, and an `ask` default in `fakeApi()`; verify `npm test` in `pwa/` passes
- [x] 5.2 Write failing tests in `screens/Ask.test.tsx` for "Five tabs", "Typed question", "Example question", "Newest first" and "Blank question" (with a fake `speechSynthesis` on `window`); verify they fail
- [x] 5.3 Implement `screens/Ask.tsx` (form, example chips, answer list, speaking), add the `"ask"` tab with the `Mic` icon, and make the nav `grid-cols-5`, to make 5.2 pass
- [x] 5.4 Write failing tests for "No speech synthesis", "Viewer asks" and "Request fails" (the API rejects with `Offline`); then make them pass, keeping the typed text on failure
- [x] 5.5 Write failing tests for "Spoken question", "No speech recognition", "Nothing heard" and "Stop listening", using a fake `SpeechRecognition` class on `window`; then add the mic button and listening state, and verify they pass
- [x] 5.6 Run `npm run typecheck` and `npm test` in `pwa/`; verify both are green and the existing App, Fridge and DemoMode tests still pass with five tabs

## 6. Docs and integration check

- [x] 6.1 Add an "Ask screen" paragraph to the README's "Voice and MCP" section (example questions, browsers with speech input, that it works for the demo passcode); verify the README renders and no product name includes "Alexa"
- [x] 6.2 Run the full suite and linters: `uv run pytest` and `uv run ruff check src tests` in `backend/`, then `npm test` in `infra/` and in `pwa/` (plus `npm run typecheck` in `pwa/`). Verify all are green and report the commands and results
- [x] 6.3 Run the PWA locally with `npm run dev`, open `#ask` at 360 px wide, and verify five tabs fit without horizontal scroll. The chips and text box should send through the fake or dev API, and the mic should appear in Chrome
