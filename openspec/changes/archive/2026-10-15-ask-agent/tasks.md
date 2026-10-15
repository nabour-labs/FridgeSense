# Tasks

## 1. Answer cleanup and tool specs (fridge-assistant)

- [x] 1.1 Write failing tests in `tests/test_assistant_clean.py` for "Thinking and markdown removed" (plus a leading `1. ` marker and collapsed newlines); run `uv run pytest tests/test_assistant_clean.py` and verify they fail because `fridgesense.assistant` doesn't exist
- [x] 1.2 Implement `clean()` in `fridgesense/assistant.py` to make 1.1 pass; verify with the same command
- [x] 1.3 Write failing tests for "MCP URL" (`mcp_url(host, key)`) and for mapping MCP tools to Converse `toolSpec`s (the "Four tools offered" shape, built from `build_server(...)`'s `list_tools()` in-process); then implement `mcp_url()` and `tool_specs()` and verify they pass

## 2. Tool-use loop (fridge-assistant)

- [x] 2.1 Add canned Converse responses under `tests/fixtures/converse/` (`tool_use_find_milk.json`, `tool_use_inventory.json`, `tool_use_find_eggs.json`, `tool_use_two_finds.json`, `tool_use_last_opened.json`, `end_turn_milk.json`, `end_turn_hello.json`, `end_turn_thinking_only.json`), each with `usage`; add a `converse_stub` fixture (botocore Stubber on `bedrock-runtime`) in `tests/conftest.py`. Verify with `uv run pytest tests/test_fixtures.py`
- [x] 2.2 Write failing tests in `tests/test_assistant_loop.py` for "Four tools offered", "Do I have milk", "System prompt" and "No tool needed", running `assistant.run()` against an in-process `build_server` over a moto table seeded with `mcp_helpers`; verify they fail for the right reason
- [x] 2.3 Implement `run()`: `Client(server)`, `list_tools`, the Converse loop with the system prompt and `inferenceConfig`, `call_tool`, `toolResult` messages, and `AssistantResult(answer, tools, usage)` to make 2.2 pass
- [x] 2.4 Write failing tests for "Open question combines tools", "Two tools in one turn" and "No camera linked" (the server context raises `ToolError(NOT_LINKED)`); then make them pass
- [x] 2.5 Refactor `run()` (message building, tool dispatch) with `tests/test_assistant_*.py` green; run `uv run ruff check src tests`

## 3. Failures, limits and cost (fridge-assistant)

- [x] 3.1 Write failing tests for "Bedrock error" (Stubber `add_client_error("converse", "ThrottlingException")`), "Too many rounds" (4 tool-use responses, no 5th queued), "Too slow" (fake clock past 12 s; Stubber asserts no further call) and "Empty answer"; then implement `AssistantFailure` and the round cap, deadline and empty checks, and verify they pass
- [x] 3.2 Write failing tests for "MCP server unreachable" with `Client("http://127.0.0.1:9/mcp/x")` (no Converse call made); then map connection and MCP errors to `mcp_error` and verify they pass
- [x] 3.3 Write failing tests for "Answered question" and "Failed question still logs cost" with `caplog` (one `ask_agent` event, summed tokens, `usd` 0.001084, no question text, no URL); then implement the cost logging with `analysis.cost_usd` and verify they pass
- [x] 3.4 Write the integration test in `tests/test_assistant_http.py`: serve `handlers.mcp.build_app("/mcp/k1")` with uvicorn on `127.0.0.1:<free port>` in a thread, answer "Do I have milk" by URL with Converse stubbed, and check that `/mcp/wrong` gives `mcp_error`; make it pass and verify with `uv run pytest tests/test_assistant_http.py`

## 4. Daily budget (fridge-assistant)

- [x] 4.1 Write failing tests in `tests/test_ask_budget.py` (moto) for "Under the limit", "Limit reached" and "New day" (household time zone); verify they fail because `increment_below` doesn't exist
- [x] 4.2 Implement `FridgeTable.increment_below()` (conditional `ADD`) and the `ASKBUDGET#<local date>` check, done before connecting to MCP and reporting `over_budget`, to make 4.1 pass; verify Converse isn't called when over budget

## 5. Polly voice (inventory-api)

- [x] 5.1 Write failing tests in `tests/test_voice.py` for "Audio returned" (Stubber on `polly`, `StreamingBody(b"ID3fake")`, expected params) and "Polly fails" (`ServiceFailureException` → `None`, `voice_failed` logged); verify they fail because `fridgesense.voice` doesn't exist
- [x] 5.2 Implement `voice.speak()` to make 5.1 pass; verify with `uv run pytest tests/test_voice.py`

## 6. `/api/ask` route (inventory-api)

- [x] 6.1 Write a failing test that `web.Request.from_event` keeps `requestContext.domainName` as `host`; then add it and verify it passes
- [x] 6.2 Update `tests/test_api_ask.py`: the existing "Do I have milk", "Viewer can ask", "Unknown question" and "Activity in the household time zone" now expect `source` `"keywords"` and an `audio` key (assistant off, Polly stubbed). Add failing tests for "Assistant answers", "Assistant off by setting", "No MCP key" and "Assistant fails" (each failure name, plus an unexpected exception → `internal_error`), patching `assistant.run` at the module boundary; verify they fail
- [x] 6.3 Implement the new `post_ask` flow (gate on `ASK_AGENT` and `mcp_key`, `asyncio.run(assistant.run(...))` with the URL from `req.host`, keyword fallback, `voice.speak`) to make 6.2 pass; add tests that the Polly "Audio returned" and "Polly fails" scenarios hold through the route, and verify with `uv run pytest tests/test_api_ask.py`
- [x] 6.4 Run the full backend suite `uv run pytest` and `uv run ruff check src tests`; both green

## 7. Infra (CDK)

- [x] 7.1 Write failing assertions in `infra/test/stack.test.ts`: API Lambda timeout 20 s; env `ASK_AGENT` (`on`), `ASK_AGENT_DAILY_LIMIT` (`100`), `NOVA_MODEL_ID`; IAM `bedrock:InvokeModel` on the Nova inference profile ARN; `polly:SynthesizeSpeech`. Run `npm test` in `infra/` and verify they fail
- [x] 7.2 Export `bedrockResources` from `door-pipeline.ts`, add `askAgent`/`askAgentDailyLimit` context, and update `app-site.ts` (timeout, env, IAM) to make 7.1 pass; verify `npm test` and `npx cdk synth` succeed (no deploy)

## 8. Ask screen (inventory-app)

- [x] 8.1 Update the `AskResult` type in `pwa/src/api/client.ts` (`source`, `audio`, `data`) and its `client.test.ts` case; verify with `npm test` in `pwa/`
- [x] 8.2 Write failing tests in `Ask.test.tsx` for "Thinking", "Plays the voice audio" (a stub `Audio` with `play` resolving), "Audio can't play" (`play` rejecting → `speechSynthesis.speak`), "Tools checked", "Keyword answer has no tools line" and "Leaving stops the voice" (unmount → `pause`), and update "Typed question" and "No speech synthesis" for `audio: null`; verify the new ones fail
- [x] 8.3 Implement the audio ref (created on the first tap), playback with speech fallback, the "Checked:" line, "Thinking…" and pausing on unmount in `Ask.tsx` to make 8.2 pass; run `npm test` and `npm run lint` (if defined) in `pwa/`, green
- [x] 8.4 Check the Ask screen in the browser preview at 360 px with a fake agent answer: the "Checked:" line wraps cleanly and the page copy never says "Alexa"

## 9. Docs and wrap-up

- [x] 9.1 Update the README's "Voice and MCP" section: how the Ask screen now uses the assistant over MCP, the `askAgent` and `askAgentDailyLimit` context values, Polly, the keyword fallback, and the per-question cost log; verify the README renders and no product name includes "Alexa"
- [x] 9.2 Add the friction log entry "Strands requires `mcp<2.2`, conflicts with the MCP server's `mcp>=2.3`" (Strands/MCP, Medium), using the exact pins from `pip index`/PyPI metadata, plus any friction hit during this change
- [x] 9.3 Run every suite: `uv run pytest` and `uv run ruff check src tests` in `backend/`, and `npm test` in `pwa/` and `infra/`; all green. Report the commands and results
- [x] 9.4 With Jayson's OK only: `cdk deploy`, then ask "Do I have milk?", "What's in my fridge?" and "What can I cook tonight?" on the deployed Ask screen; confirm `source: "agent"`, the audio plays, and the `ask_agent` cost logs show a sensible `usd`
