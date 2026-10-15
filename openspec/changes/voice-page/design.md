# Design

## Context

- **Answers:** `fridge_answers.py` already has pure functions that take a table, an account and a clock and return Pydantic models: `find_item`, `inventory`, `activity` and `last_opened`. The MCP tools wrap them, and they were checked against the live table on Oct 15 with seeded demo data, at 110–210 ms per call from the Mac.
- **API:** the app API Lambda (`handlers/api.py`) routes `/api/*` with `@route(method, path, write=False)`. It checks the bearer token, refuses writes for viewers, and gives each handler a `Context` with the account and table. API Gateway already sends `ANY /api/{proxy+}` to it, so a new route needs no infra route.
- **Time zone:** the API Lambda has no `TIME_ZONE` env today; only the MCP Lambda gets it from CDK context `timeZone`.
- **PWA:** tabs are a `TABS` array in `App.tsx`, the `Tab` type, and hash routing. Screens get the API and `report()` from `AppContext`, and tests inject `fakeApi()`.

See proposal.md for scope.

## Goals / Non-Goals

**Goals:**
- Voice and Alexa+ say the same facts, because both read the same answer functions.
- A round trip fast enough to feel like a voice assistant: one Lambda call and one or two DynamoDB queries.

**Non-Goals:**
- Natural-language coverage beyond the demo questions and close variants.
- Saving the question history (it lives in component state only).

## Decisions

### Intent matching: ordered keyword rules in one pure module
- `fridgesense/ask.py` has `parse(question) -> Intent`, where `Intent` holds the name plus `item`, `category` or `period`. It normalizes the question (lower case, punctuation stripped, spaces collapsed), then tries rules in the spec's order: last opening, activity, item, inventory.
- Item extraction strips the lead-in, articles and trailing filler from fixed lists. A leftover item that is a category name or alias becomes an inventory question.
- `ask(table, account_id, question, now, tz) -> AskResult(intent, answer, data)` calls `parse`, then the matching `fridge_answers` function, then a `say_*` function that turns the model into a sentence. `unknown` returns the hint without touching the table.
- *Alternative:* send unmatched questions to Nova Micro through Converse with the four tools. That's more natural, but it adds cost, latency and stubs for every test, and the demo questions are known. It stays a stretch goal; `ask()` is the one place to add it.
- *Alternative:* match intents in the browser and call the existing GET routes. That would duplicate the answer logic in TypeScript and drift from what the MCP server says.

### Sentences live next to the answers, not in the PWA
- The `say_*` functions sit in `ask.py`, take the Pydantic results, and are unit-tested with plain objects.
- Plurals use one rule: add "s" when count ≠ 1 and the name doesn't end in "s". "2 milks" is accepted for the demo; a per-item plural table isn't worth it.
- The time phrase (`ago(minutes)`) is shared by the item and last-opening sentences.

### Route: `POST /api/ask`, read-only
- `@route("POST", "/api/ask")` with `write=False`, so viewers pass. It parses the body with the existing `_json_body` and validates `question` (a string, non-blank, at most 200 characters), else 400.
- It's a POST rather than `GET /api/ask?q=` because questions don't belong in URLs or access logs. CloudFront doesn't cache `/api/*` either way.
- It uses `ZoneInfo(os.environ.get("TIME_ZONE") or "America/Toronto")`, the same default as the MCP context.

### Infra: pass `TIME_ZONE` to the API Lambda
- `AppSite` gets a `timeZone` prop, and the stack passes the same `context("timeZone", "America/Toronto")` value it gives `McpEndpoint`. A CDK assertion test checks the env var.
- This is the only infra change, and it needs a `cdk deploy`.

### PWA: an Ask screen with injectable browser speech
- `screens/Ask.tsx` keeps a list of `{question, answer}` in state, newest first.
- Its parts: a text form (send button), three example chips, and a mic button shown only when `window.SpeechRecognition ?? window.webkitSpeechRecognition` exists.
- Recognition settings: `lang = "en-US"`, `interimResults = false`, `maxAlternatives = 1`. `onresult` posts the first final transcript. `onerror`, or `onend` without a result, shows the "Didn't catch that" message.
- Speaking calls `speechSynthesis.cancel()` and then `speak(new SpeechSynthesisUtterance(answer))` when `speechSynthesis` exists.
- Errors go to `report()`, so the offline banner and sign-out work as on other screens. The typed text is cleared only after a successful answer.
- **Tab bar:** `Tab` gains `"ask"`. `TABS` adds `{ id: "ask", label: "Ask", Icon: Mic }` from lucide-react, and the nav grid becomes `grid-cols-5`.
- **Copy:** the page is "Ask", never "Alexa".

## Risks / Trade-offs

- **[Risk] iOS Safari speech recognition is flaky or needs Siri enabled.** → The text box and example chips always work, and the demo video can use desktop Chrome.
- **[Risk] Speech synthesis is silent until a user gesture on iOS.** → Every answer follows a tap (send, chip or mic), which counts as the gesture.
- **[Risk] Keyword rules miss phrasings judges try.** → The `unknown` hint lists working questions, and the example chips show the format. Rules are table-driven, so adding a phrase is a one-line test plus one-line change.
- **[Trade-off] Five tabs on a 360 px phone.** → The labels are short ("Ask" is the shortest). The tab bar's existing layout is checked at 360 px in the browser after the change.
- **[Risk] Pluralization slips ("2 milks", "3 cheddar cheeses").** → Accepted for the demo.

## Migration Plan

1. Merge into `local` with tests green, then `cdk deploy`. This adds `TIME_ZONE` to the API Lambda and ships the new Lambda code. CDK's `BucketDeployment` ships the PWA build.
2. **Rollback:** redeploy the previous commit. The route and tab are additive, and no data changes.

## Test strategy

- **Unit (pytest), `tests/test_ask_parse.py`:** one test per intent scenario in `fridge-ask` (ordering, normalization, lead-ins, categories and aliases, unknown), on `parse()` only.
- **Unit (pytest), `tests/test_ask_say.py`:** sentence scenarios built from hand-made `FindItemResult`, `InventoryResult`, `ActivityResult` and `LastOpenedResult` objects, plus `ago()` and plural cases. No table.
- **Integration (pytest + moto), `tests/test_api_ask.py`:**
  - the route end to end through `api.handler`, with the existing `aws` fixture, `link_account()`, `sign_in()` and seeded `ITEM#`/`DOOR#` rows
  - owner and viewer tokens, 400 bodies and 401
  - the time-zone scenario with `TIME_ZONE` set via monkeypatch and `api.now` fixed
  - "unknown doesn't query" by asserting the stubbed table's `query` isn't called
- **CDK (Vitest + assertions), `infra/test/site.test.ts`:** the API function has `TIME_ZONE` `America/Toronto` by default, and the context value when one is given.
- **PWA (Vitest + Testing Library), `screens/Ask.test.tsx`:**
  - `fakeApi({ ask })` with a new `ask` default in `test-utils.tsx`
  - fake `SpeechRecognition` and `speechSynthesis` classes installed on `window` per test and removed after
  - covers every Ask screen and Speak a question scenario, including the five-tab nav and viewer role
  - `client.test.ts` covers `ask()` posting `{question}` to `/api/ask`
- **Fixtures:** no new files. Rows are built in the tests, as the existing API tests do. Nothing calls live AWS, Ring or Bedrock.
- **Manual check after deploy:** ask the three example questions on the phone against the demo rows, with voice in Chrome and Safari.
