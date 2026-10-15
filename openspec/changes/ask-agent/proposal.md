# Proposal

## Why

There's no Echo for the demo, and Alexa+ MCP Toolkit access may be gated, so the Alexa+ part of the video has to be simulated. Today the Ask screen calls `/api/ask`, which matches keywords in `ask.py` and reads `fridge_answers` directly. It never touches the MCP server, so it shows nothing of what the Alexa+ track checks: a model that discovers and calls our MCP tools over Streamable HTTP. A small stand-in for Alexa+'s model, a Nova tool-use loop that is a real MCP client of our own server, makes the simulated experience honest, and it can also answer open questions ("what can I cook tonight?") that keyword rules can't.

Tracks: **Alexa+** (a real MCP round trip over Streamable HTTP, spec 2025-11-25, driven by a model choosing tools) and **AWS Builder** (Bedrock Converse tool use with Nova, Amazon Polly).

## What Changes

- **Fridge assistant:** a new backend module answers a question by connecting to the deployed MCP server at `/mcp/<key>` as an MCP client, listing its tools, and running a Bedrock Converse tool-use loop with Nova 2 Lite. It returns a short sentence for speaking, plus the tools it called. It has a time limit, a cap on rounds, a daily question budget, and logs Nova tokens and USD cost for every question.
- **`POST /api/ask` tries the assistant first** and falls back to the existing keyword rules when the assistant is off (no `mcp_key`, or `ASK_AGENT` disabled), over budget, too slow, or fails. The response gains `source` (`"agent"` or `"keywords"`) and `audio`. Agent answers use intent `"agent"`, with `data` `{"tools": [...]}`.
- **Polly voice:** every answer, from either source, is synthesized with Amazon Polly (neural voice, MP3) and returned as base64 `audio`. If Polly fails, `audio` is `null`.
- **Ask screen:** plays `audio` when present and falls back to browser speech synthesis otherwise. For agent answers it shows a small "Checked: find_item, …" line under the answer, so the video can show the MCP tools at work. Speech recognition for input is unchanged. The page is still called "Ask", never "Alexa".
- **Infra:** the API Lambda gets `bedrock:InvokeModel` on the Nova inference profile, `polly:SynthesizeSpeech`, a longer timeout (20 s, under API Gateway's 30 s cap) and the `ASK_AGENT`/`NOVA_MODEL_ID` env. Needs a `cdk deploy`.
- **No Strands:** Strands 1.61 requires `mcp<2.2`, but the backend's MCP server needs `mcp>=2.3`. The loop uses the MCP SDK's own `Client` with Bedrock Converse instead (see design.md). This goes in the friction log.

## Capabilities

### New Capabilities
- `fridge-assistant`: answers a free-text fridge question with Nova acting as an MCP client of the FridgeSense MCP server: tool discovery, the tool-use loop, the spoken-answer style, time and round limits, the daily budget and cost logging.

### Modified Capabilities
- `inventory-api`: "Ask a fridge question" changes. The route tries the assistant first and falls back to keywords, and the response adds `source` and `audio`, with intent `"agent"` for assistant answers.
- `inventory-app`: "Ask screen" changes. It plays the Polly audio when it's there, falls back to speech synthesis, and shows the tools checked for assistant answers.

## Out of scope

- Strands, or any agent framework.
- A real Alexa+ integration, an Echo emulator, or a wake word. If toolkit access arrives, that's a separate change.
- Streaming audio or partial answers. Amazon Transcribe for speech input (browser recognition stays).
- Saving question history or conversation memory across questions: each question is answered on its own.
- Recipes from outside the fridge data: "what can I cook" uses only what the tools return plus the model's general knowledge.
- Changes to the MCP server, its tools or the keyword rules.

## Impact

- **Backend:** new `fridgesense/assistant.py` (Converse loop plus MCP client) and `fridgesense/voice.py` (Polly). `handlers/api.py` `post_ask` changes, and `web.Request` gains the API host (`requestContext.domainName`) to build the MCP URL. New daily budget counter item in the table (`pk` = account, `sk` = `ASKBUDGET#<local date>`).
- **PWA:** `screens/Ask.tsx` and its tests; the `api.ask` return type gains `source`, `audio` and `data`.
- **Infra:** `app-site.ts` (IAM, timeout, env) and `stack.test.ts` assertions.
- **Dependencies:** none new. `mcp` (already pinned `>=2.3`) provides the client, and boto3 is in the Lambda runtime.
- **Cost:** about 2–3 Nova 2 Lite calls per question (well under $0.01) plus Polly (about $0.0005 for a 30-word answer), capped by the daily budget (default 100 agent questions per day). Live Bedrock and Polly calls happen only after deploy, with Jayson's OK.
- **Docs:** README "Voice and MCP" section, friction log entry (Strands and MCP version conflict).
