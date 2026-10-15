# Proposal

## Why

Every Nova call sends its whole prompt again: the door-opening analysis resends the owner's reference images each time, and the Ask assistant resends the system prompt, the tool specs and every earlier round in each of its up-to-4 rounds, all within a 12 s voice deadline. Bedrock prompt caching (Converse `cachePoint`) can serve those repeated prefixes from cache, which is faster and cheaper. There is also a bug waiting to happen: once any caching occurs (Nova already caches text prefixes implicitly), Converse reports `inputTokens` as the *uncached* tokens only, and our cost log ignores `cacheReadInputTokens` and `cacheWriteInputTokens`. That undercounts spend, and the AWS bill is paid out of pocket.

## What Changes

- **Cost accounting counts cached tokens.** Analysis (`nova_cost`, `nova_usd`) and the assistant (`ask_agent`) read `cacheReadInputTokens` and `cacheWriteInputTokens` from Converse usage, log them as `cache_read_tokens` and `cache_write_tokens`, and price them with new settings `NOVA_PRICE_CACHE_READ` and `NOVA_PRICE_CACHE_WRITE`. A response with no cache fields costs exactly what it costs today.
- **Every LLM call is tracked (new `llm-usage-tracking` capability).** Each Nova call logs one shared `llm_usage` event: source (`analysis` or `assistant`), account, model, input, output, cache-read and cache-write tokens, total input tokens and `usd`. The call's counts are also added atomically to a per-account daily item (`ACCOUNT#<id>` / `USAGE#<YYYY-MM-DD>`, household time zone), with per-source call counts and cost. That keeps spend checkable after CloudWatch logs expire. A failed totals write only logs a warning; it never breaks an analysis or an answer.
- **Assistant requests carry a cache point.** The system block (system prompt, with the tool specs ahead of it) ends with a `cachePoint`, so each round reads that prefix from cache. Messages carry none: the measurement showed Nova 2 Lite rejects a cache point after a `toolResult` block. None goes in `toolConfig`, which Nova doesn't accept, and no `ttl` is sent.
- **Analysis requests can carry cache points, off by default.** With `NOVA_CACHE_ANALYSIS` on, the request gets a `cachePoint` after the reference images (when there are any) and one after the stills, so a burst of door openings shares the references and the invalid-answer retry hits the cache. Content order and wording are unchanged. With the setting off (the default), the request is byte-for-byte what it is today.
- **A one-off measurement script** (`backend/scripts/measure_prompt_cache.py`, run by hand only with Jayson's OK because it calls Bedrock) sends a reference-image analysis request and a 2-round assistant-shaped request twice each. It reports token counts for cache reads and writes, plus latency, to show whether Nova 2 Lite caches image prefixes and accepts cache points after tool results. The analysis setting is only turned on if it does.
- CDK passes the two cache prices and the analysis switch to both Lambdas as context values with defaults.

Hackathon track: **AWS Builder** (Bedrock Nova cost and latency), with a secondary benefit to **Alexa+** (faster answers for the voice assistant's MCP-driven questions).

### Out of scope

- The 1-hour TTL (Nova supports only 5 minutes), and keeping the cache warm with extra calls.
- Caching for anything other than the two existing Converse call sites. Alexa+'s own model calls our MCP server, and we don't control its prompts.
- Reordering or rewording the analysis prompt (for example, moving the rules into `system`). The small text that changes between door openings stays after the cache points.
- Switching models, batch inference, or adding a new inventory-snapshot cache layer.
- A usage API endpoint or a usage screen in the PWA. The daily items are shaped so either can be added later.
- Turning `NOVA_CACHE_ANALYSIS` on in the deployed stack. That's a deploy-time decision after the measurement.

## Capabilities

### New Capabilities

- `llm-usage-tracking`: per-call token, cached-token and cost records for every LLM call, the shared cost formula, and daily per-account usage totals in DynamoDB.

### Modified Capabilities

- `fridge-change-analysis`: cost logging counts cache read and write tokens; new opt-in requirement for cache points in the analysis request.
- `fridge-assistant`: cost logging counts cache read and write tokens; new requirement for cache points in each assistant request.

## Impact

- Code: a new `backend/src/fridgesense/usage.py` (token counts from Converse usage, the cost formula, the recorder that logs `llm_usage` and adds to the daily totals), `FridgeTable.add_many` in `table.py`, `inventory.analyze_task` (passes a recorder), `backend/src/fridgesense/analysis.py` (`Usage`, `cost_usd`, `build_request`, `NovaAnalyzer.from_env`/`analyze`), `backend/src/fridgesense/assistant.py` (`_Run.spend`, `_loop`, `run` signature, `ask_agent` log), `backend/src/fridgesense/handlers/api.py` (pass the cache prices to `assistant.run`), and the new `backend/scripts/measure_prompt_cache.py`.
- Data: new `USAGE#<YYYY-MM-DD>` items under each account's partition, one per day with LLM calls. They're small and kept indefinitely.
- Infra: `infra/lib/fridgesense-stack.ts`, `app-site.ts`, `door-pipeline.ts` (new env vars `NOVA_PRICE_CACHE_READ`, `NOVA_PRICE_CACHE_WRITE`, `NOVA_CACHE_ANALYSIS`, and `TIME_ZONE` for the pipeline Lambda, which doesn't get it today) and their CDK tests.
- Tests: a new `test_usage.py`, `test_analysis_request.py`, `test_analysis_response.py`, `test_analyze_task.py`, `test_assistant_loop.py`, `test_assistant_failures.py`, plus unit tests for the script's pure helpers. Everything is stubbed. No live Bedrock.
- Cost: the measurement run is a handful of Nova 2 Lite requests (well under $0.01). After that, cost and latency should drop, and costs are logged accurately.
