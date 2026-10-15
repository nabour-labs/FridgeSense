# Design

## Context

- **Ask today:** `POST /api/ask` (`handlers/api.py` `post_ask`) validates the question and calls `ask.ask()`, which runs keyword rules in front of `fridge_answers` and returns `AskResult(intent, answer, data)`. The PWA's `Ask.tsx` posts, shows the answer and calls `speechSynthesis`.
- **MCP server:** `mcp_server.build_server(context)` builds an `MCPServer` with four read-only tools. The MCP Lambda serves it statelessly at `/mcp/{key}` on the **same HTTP API** as `/api/{proxy+}`, with JSON responses, and returns 404 for a wrong key.
- **MCP SDK:** the backend pins `mcp>=2.3,<3`. Its `mcp.Client` accepts a URL (Streamable HTTP) or, in tests, an `MCPServer` instance connected in-process. It has `list_tools()` and `call_tool()` and is async.
- **Nova:** `analysis.py` already calls Converse with `us.amazon.nova-2-lite-v1:0`, reads `NOVA_MODEL_ID`/`NOVA_PRICE_IN`/`NOVA_PRICE_OUT`, and has `cost_usd()` (decimal, half-up, 6 places). `door-pipeline.ts` has `bedrockResources()` for the inference-profile IAM ARNs.
- **Strands:** `strands-agents` 1.61 requires `mcp<2.2,>=1.23`, which conflicts with our `mcp>=2.3`. Jayson chose a hand-written loop over a second Python project.
- **API Lambda:** 256 MB, 10 s timeout. API Gateway HTTP API cuts integrations off at 30 s.
- **Request:** `web.Request` doesn't keep `requestContext.domainName` today.

## Goals / Non-Goals

**Goals:**
- A real MCP round trip over Streamable HTTP for every assistant answer, driven by the model's tool choice, visible in logs and on screen ("Checked: …").
- The demo never breaks: any assistant problem falls back to the keyword answer within the same request.
- A voice that sounds like a smart speaker, and bounded, logged cost.

**Non-Goals:**
- An agent framework, multi-turn memory, streaming.
- Changes to the MCP server or the keyword rules.

## Decisions

### Loop: Bedrock Converse tool use plus `mcp.Client`, in `fridgesense/assistant.py`
- `async def run(question, *, server, bedrock, model_id, prices, clock, deadline_s=12, max_rounds=4) -> AssistantResult | AssistantFailure`. `server` is the MCP URL in production and an `MCPServer` in tests. The `mcp.Client` API is the same for both.
- Steps: open `Client(server)` → `list_tools()` → map each tool to a Converse `toolSpec` (`name`, `description`, `inputSchema: {"json": tool.inputSchema}`) → loop: `converse(modelId, system, messages, toolConfig, inferenceConfig={"maxTokens": 300, "temperature": 0.2})`. On `stopReason == "tool_use"`, call every `toolUse` block through `client.call_tool(name, input)` and append one user message with all `toolResult` blocks. Content is `[{"json": structuredContent}]` when the tool returns structured output, otherwise `[{"text": …}]`. `status` is `"error"` when `isError`. On `end_turn`, clean the text and return.
- Converse is a blocking boto3 call, so it runs in `anyio.to_thread.run_sync`. The whole run sits in `anyio.fail_after(deadline_s)`. An injected `clock` is checked before each model and tool call, which keeps the timeout test deterministic. The Bedrock client is `Config(read_timeout=10, retries={"total_max_attempts": 1})`, following the friction log note: `max_attempts: 1` still makes two attempts.
- Failures are a small enum: `mcp_error`, `bedrock_error`, `too_many_rounds`, `timeout`, `empty_answer`, `over_budget`. `run` never raises for these. Programming errors still raise, and `post_ask` catches them as `internal_error` so it can fall back (logged at ERROR).
- *Alternative:* Strands in its own Lambda and project, pinned to `mcp<2.2`. It keeps the Strands name for AWS Builder, but costs a second project, a Lambda-to-Lambda hop and a heavier cold start. Rejected for the deadline.
- *Alternative:* call `fridge_answers` in-process as Converse tools. It's simpler, but it isn't MCP, which defeats the purpose.

### MCP URL from the incoming request
- `web.Request` gains `host` (`requestContext.domainName`). The assistant URL is `https://{host}/mcp/{mcp_key}`.
- A `McpEndpoint`/`api.url` env var on the API Lambda would create a circular CDK dependency (API → integration → Lambda → API). The request host avoids it. Through CloudFront, `domainName` is still the execute-api host that API Gateway sees.
- The URL contains the key, so it is never logged; `log_event` gets only `outcome`/`tools`/tokens.

### Spoken style
- The system prompt says: you're FridgeSense, a kitchen voice assistant. Answer in at most two short spoken sentences, no markdown or lists. Use the tools for any fact about the fridge, and say counts and how long ago. If an item ran out, say so. For "what can I cook", suggest one or two ideas from what's in stock.
- `clean()` removes `<thinking>…</thinking>` (Nova 2 Lite emits it around tool use), `* _ # \``, leading `- ` or `1. ` markers, and collapses whitespace. It's a pure function with its own unit tests.

### Budget: one conditional counter per day
- `FridgeTable.increment_below(pk, sk, field, limit) -> bool`: `UpdateItem ADD #f :one` with `ConditionExpression attribute_not_exists(#f) OR #f < :limit`. `ConditionalCheckFailedException` → `False`.
- Key: `pk = account_pk(account)`, `sk = ASKBUDGET#<YYYY-MM-DD local>`. It's one tiny item per day, so no TTL is needed.
- It's checked before connecting to MCP, so an over-budget question costs nothing. Default limit 100 (`ASK_AGENT_DAILY_LIMIT`). At about $0.001 per question, that caps Nova spend near $0.10 a day.

### Route flow (`post_ask`)
1. Validate (unchanged).
2. If `ASK_AGENT == "on"` and `mcp_key` is set: `asyncio.run(assistant.run(...))`. On success the response is `{intent: "agent", answer, data: {"tools": [...]}, source: "agent"}`.
3. Otherwise, or on failure: `ask.ask(...)` with `source: "keywords"`.
4. `voice.speak(answer)` → base64 or `None`; set `audio`.
- `ASK_AGENT` is a CDK context value (`askAgent`, default `"on"`), so it can be switched off with a deploy if costs surprise us.

### Voice: Polly in `fridgesense/voice.py`
- `speak(text, client, voice="Joanna") -> str | None`: `synthesize_speech(Text, Engine="neural", VoiceId, OutputFormat="mp3", SampleRate="24000")`. It reads `AudioStream` and returns base64. Any `ClientError`/`BotoCoreError` → `None`, logged as `voice_failed`.
- Audio goes inline in the JSON (a two-sentence answer is roughly 20–40 KB of MP3). That's one request and no S3 or presigned URLs. API Gateway's 10 MB payload limit is far away.
- *Alternative:* a separate `/api/speak` route. That's an extra round trip after the answer, so the voice starts later. Rejected.

### PWA
- `AskResult` type gains `source`, `audio: string | null`, and `data`.
- `Ask.tsx` keeps one `HTMLAudioElement` in a ref, created on the first tap so the user gesture unlocks it on iOS. On an answer with `audio`, it sets `src = "data:audio/mpeg;base64,…"` and calls `play()`; on rejection it calls `speak(answer)`. Without `audio` it calls `speak(answer)` as today. The unmount cleanup pauses the audio as well as cancelling speech.
- A history entry stores `tools` when `source === "agent"`, and the answer renders `Checked: a, b` in muted small text. "Thinking…" shows while `busy`.

### Infra (`app-site.ts`)
- Timeout 10 s → 20 s (12 s deadline plus keyword fallback plus Polly, under the 30 s HTTP API cap). Memory stays 256 MB.
- `bedrock:InvokeModel` on `bedrockResources(stack, novaModelId)` (export and reuse it from `door-pipeline.ts`), and `polly:SynthesizeSpeech` on `*` (Polly has no resource ARNs).
- Env: `ASK_AGENT`, `ASK_AGENT_DAILY_LIMIT`, `NOVA_MODEL_ID` (the same context value as the pipeline). `TIME_ZONE` is already there.

## Test strategy

- **Unit (pytest):**
  - `clean()` cases; tool-spec mapping from an MCP tool list; `mcp_url(host, key)`.
  - Assistant loop with an **in-process MCP server** (`build_server` over a moto table seeded with `mcp_helpers`) and **botocore Stubber** on `bedrock-runtime` `converse`. Canned responses in `tests/fixtures/converse/` (`tool_use_find_item.json`, `tool_use_two.json`, `end_turn_milk.json`, `end_turn_thinking.json`, …). These cover the four-tools-offered, Do I have milk, combine, two-in-one-turn, no-tool, tool-error (a server context raising `ToolError(NOT_LINKED)`), too-many-rounds, timeout (fake clock), empty-answer and bedrock-error scenarios. The cost log is asserted with `caplog`.
  - MCP unreachable: `Client("http://127.0.0.1:9/mcp/x")` (connection refused, local only) → `mcp_error`, Stubber has no queued responses.
  - Budget: `increment_below` on moto (under, at the limit, new day).
  - Voice: Stubber on `polly` `synthesize_speech` (success with a `StreamingBody`, `ServiceFailureException`).
- **Contract (pytest, API handler):** `post_ask` with the assistant patched at the module boundary (`assistant.run` returns a success or each failure), Polly stubbed. Covers the new response fields, the fallbacks, the agent off/no-key cases (Stubber asserts no Converse call) and the existing Ask scenarios with `source: "keywords"`.
- **Integration (pytest, local only):** one test runs the real MCP Starlette app (`handlers.mcp.build_app("/mcp/k1")`) with uvicorn (it ships with `mcp`) on `127.0.0.1:<free port>` in a thread. `assistant.run` connects by URL, which proves the Streamable HTTP client path end to end with Converse stubbed. A request to `/mcp/wrong` gets 404 → `mcp_error`.
- **PWA (Vitest):** `Ask.test.tsx` with `fakeApi()` returning `audio`/`source`/`data`. A stub `Audio` (`play` resolving or rejecting, `pause` spy) and the existing `speechSynthesis` stub. Covers plays audio, play rejected → speech, no audio → speech, tools line, no tools line for keywords, Thinking…, and pausing on unmount.
- **CDK (Vitest assertions):** API Lambda timeout 20, env vars, IAM statements for `bedrock:InvokeModel` (inference profile ARN) and `polly:SynthesizeSpeech`.
- **Not automated:** the live check after deploy (one question each for milk, inventory and "what can I cook", watching `ask_agent` cost logs). It needs Jayson's OK because it calls Bedrock and Polly.

## Risks / Trade-offs

- **[Risk] Nova picks the wrong tool or invents facts.** → The system prompt forces tools for fridge facts, temperature is 0.2, and the "Checked:" line makes a wrong path visible. Keyword fallback can't catch a confident wrong answer, but the demo questions are known and get checked live.
- **[Risk] Latency:** 2 Nova calls (~1–2 s each) + MCP (~0.2 s per call, plus a cold start on the MCP Lambda) + Polly (~0.3 s) ≈ 3–5 s. → "Thinking…" covers the wait. The MCP Lambda already has a warmup event, and a cold MCP start inside the 12 s deadline is fine.
- **[Risk] The MCP Lambda calls back into the same API (Lambda → API Gateway → Lambda).** → It's stateless and read-only, the key gates it, and there's no recursion (the MCP Lambda never calls `/api/ask`).
- **[Risk] iOS blocks `audio.play()` after an `await`.** → The audio element is created during the tap, and a rejected `play()` falls back to speech synthesis. The video is recorded on desktop Chrome.
- **[Trade-off] Viewers (the demo passcode) can spend Nova money.** → The daily budget, the 200-character question limit and the ability to turn `ASK_AGENT` off.
- **[Trade-off] No Strands.** The AWS Builder write-up rests on Bedrock Converse tool use, Polly and CDK. The Strands/MCP version conflict goes in the friction log and the product feedback.
