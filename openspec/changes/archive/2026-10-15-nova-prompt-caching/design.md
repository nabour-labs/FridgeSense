# Design

## Context

Two Converse call sites use Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`):

- `analysis.build_request` sends one user message per door opening. The order is: reference header, then the references (up to 6 JPEGs of ≤200 KB each, oldest first), then up to 4 stills, then a final text that holds the rules, the inventory, the owner's instructions and the tool line. `toolConfig` forces `record_fridge_changes`. The same request is sent again once if the answer is invalid.
- `assistant._loop` runs up to 4 rounds. Each round resends `system` (the static `SYSTEM_PROMPT`), the MCP tool specs (in server order) and the growing message list, all inside a 12 s deadline.

What Bedrock's docs say about prompt caching on Nova (see the [prompt caching guide](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)):

- Explicit `cachePoint` blocks are allowed in `system` and `messages` only, not `tools`.
- A request can have at most 4 cache points.
- The prefix before a cache point has to total at least about 1K tokens, counting tools, then system, then messages. A shorter prefix doesn't cache, but the request still succeeds.
- The cache holds at most 20K tokens and has a 5-minute TTL that resets on each hit.
- Sending `ttl` may cause a `ValidationException`.
- Nova also caches text prefixes implicitly.
- Usage reports `inputTokens` as uncached tokens only, next to `cacheReadInputTokens` and `cacheWriteInputTokens`.
- The guide says caching is "primarily for text prompts". Whether image prefixes cache is unconfirmed (see the friction log entry of 2026-10-15).

Prices come from `NOVA_PRICE_IN` / `NOVA_PRICE_OUT`. The CDK stack sets them from context values for the pipeline and app-site Lambdas, and the assistant gets them from the API handler.

## Goals / Non-Goals

**Goals:**
- Accurate cost logs whether or not caching happens.
- Cache hits on assistant rounds 2–4, and on analysis requests that share references within 5 minutes.
- Zero change to the analysis request until measurement shows image caching works.

**Non-Goals:**
- Getting the highest possible hit rate (warmers, reordering the prompt, the 1-hour TTL).
- Showing cache stats in the PWA.

## Decisions

1. **Count cached tokens separately; don't fold them into `input_tokens`.**
   - `input_tokens` stays `usage.inputTokens`, so existing scenarios and dashboards keep their meaning.
   - `cache_read_tokens` and `cache_write_tokens` are new fields.
   - `cost_usd` gains two keyword arguments that default to 0, so existing callers and tests still give the same numbers.
   - Alternative rejected: one `input_tokens` that sums all three. It hides how well caching works, and it breaks the existing `ask_agent` scenario arithmetic.

2. **Default cache prices.**
   - Confirmed on 2026-10-15 with the AWS Price List API (`aws pricing get-products --service-code AmazonBedrock`, us-east-1). For Nova 2 Lite on demand, usage types `USE1-Nova2.0Lite-cache-read-input-token-count` and `USE1-Nova2.0Lite-cache-write-input-token-count`:
     - Cache read: $0.0000825 per 1K tokens, 25% of the $0.00033 input price.
     - Cache write: $0.00. Writing to the cache costs nothing extra; those tokens aren't billed as input either.
   - Defaults: `0.0000825` for reads and `0` for writes. Both can be overridden through env and CDK context, for example for another model or a global profile, where reads are $0.000075.

3. **Analysis: insert cache points only, behind `NOVA_CACHE_ANALYSIS=true`.**
   - The references are already first. One cache point goes after them, so the account's references (stable until the owner edits them) form the shared prefix across a burst of door openings.
   - A second cache point goes after the stills. The invalid-answer retry resends the identical request, so it reads everything up to the final text from cache.
   - The final text (rules, inventory, owner's instructions) stays after both cache points. It's a few hundred tokens and the inventory changes every time.
   - Alternative rejected: moving the rules and owner's instructions into `system`. That saves little, changes the prompt Nova has been tuned against, and needs spec changes to "Owner's config sent with each analysis". It isn't worth the risk in the last week.
   - The setting is read in `NovaAnalyzer.from_env` and passed to `build_request` as a `cache: bool` argument, which defaults to False.

4. **Assistant: always on, with one cache point at the end of `system`.**
   - It covers the tool specs and the system prompt, which are byte-stable across rounds and questions.
   - The first plan also put a cache point after each tool-results message, so round N+1 would read all of round N. The measurement (measurement.md) showed Nova 2 Lite rejects a `cachePoint` after a `toolResult` block with a `ValidationException`, which would have turned every tool question into `bedrock_error`. So messages carry none.
   - If the tools-plus-system prefix is under about 1K tokens it doesn't cache, which is harmless. Nova's implicit caching may still help.
   - Alternative left for later: a short text block after the tool results, with the cache point after it. That's untested.

5. **Measurement script, not an automated test.**
   - `backend/scripts/measure_prompt_cache.py` builds requests with the real `build_request(..., cache=True)` and the assistant request shape. It sends each twice, about 2 s apart, and prints `inputTokens`, the two cache counts, and `metrics.latencyMs` for each call.
   - It reads `AWS_PROFILE` from `.env`, uses the fixture stills and a fixture reference JPEG, and refuses to run without `--yes`.
   - Pass criteria:
     - The second analysis call has `cacheReadInputTokens > 0`.
     - The second assistant round shows a read.
     - No call raises `ValidationException`.
   - Only the pure helper that summarizes usage into a table row is unit-tested.
   - The results go in the change's `measurement.md` and decide whether `novaCacheAnalysis` is set to `true` at deploy.

6. **Infra:** three new context values, all passed as strings:
   - `novaPriceCacheRead` (default `"0.0000825"`) and `novaPriceCacheWrite` (default `"0"`), to both Lambdas.
   - `novaCacheAnalysis` (default `"false"`), to the pipeline Lambda only.

7. **One shared usage module, used by both call sites (`usage.py`).**
   - `Tokens.from_converse(usage)` reads the four counts (missing = 0) and gives `total_input`. `price(tokens, prices)` applies the formula in the `llm-usage-tracking` spec, and `Prices.from_env()` reads the four price settings. `analysis.cost_usd` and `assistant._Run.spend` both delegate to it, so the formula lives in one place.
   - `UsageRecorder(table, tz, source, account_id, model_id, clock)` is a callable taking `Tokens`. It logs `llm_usage`, then calls `table.add_many(account_pk(account_id), f"USAGE#{day}", {...})`: one `UpdateItem` with `ADD` on every counter, so concurrent Lambdas never lose an increment. Any exception from the write is caught and logged as `llm_usage_store_failed`, and the recorder never raises.
   - The call sites take an optional `on_usage` callback: `NovaAnalyzer.analyze(..., on_usage=)` and `assistant.run(..., on_usage=)`. `inventory.analyze_task` and `handlers/api._ask_assistant` build the recorder, because they already have the table and the account. With no callback (most existing tests), nothing is recorded, so existing tests don't need DynamoDB.
   - The day comes from the household `TIME_ZONE`, like the assistant's daily budget, so "today" matches what the app shows. The pipeline Lambda needs `TIME_ZONE` added.
   - `nova_cost` and `ask_agent` stay as they are, beyond the new cache fields. Dashboards and specs already use them. `llm_usage` is the one event to query across both sources.
   - Alternatives rejected:
     - Totals computed from logs (CloudWatch Logs Insights): lost after log retention, and nothing in the app can read them.
     - One item per call: unbounded growth, and adding up totals means queries.
     - Moving `nova_usd` onto the usage item: the door event keeps its own cost for the per-opening view.

## Risks / Trade-offs

- [The totals write adds a DynamoDB call per LLM call, so latency rises inside the 12 s assistant deadline] → It's a single `UpdateItem` of a few milliseconds. If it ever matters, it can move out of the round loop and be done once per question.
- [The float `usd` adds up rounding drift in the DynamoDB `ADD`] → `usd` is serialized as `Decimal(str(round(usd, 6)))`. DynamoDB numbers are exact decimals, so the sums don't drift.

- [Image blocks don't cache on Nova] → Analysis caching stays off. The accounting fix and the assistant caching still ship. Record the outcome in the friction log.
- [The assistant prefix is under the 1K-token minimum] → It silently doesn't cache, which is harmless. The measurement shows whether rounds 2+ get reads anyway, because the growing message list pushes later prefixes past 1K.
- [Nova rejects a cache point after `toolResult` blocks] → Confirmed by the measurement. The assistant now caches the system block only.
- [The analysis cache points sit right after image blocks, which Nova 2 Lite rejects (measurement.md)] → `NOVA_CACHE_ANALYSIS` stays `false`. Turning it on as built would fail every analysis. Before it's ever turned on, the cache points have to move after a text block and pass a new measurement.
- [The system-only cache point hasn't been tried live] → Checked in the second measurement run: 766 tokens written, then read back.
- [Cross-region inference profile (`us.`) sends a request to another Region and causes extra cache writes] → Nova 2 Lite cache writes are free, so a miss costs no more than today. Watch `cache_write_tokens` in the logs.
- [Cache prices are wrong] → They only affect the logged `usd`, not behavior. Confirm them before deploy, and fix by changing the context value without code changes.
- [Door openings more than 5 minutes apart rarely hit] → Expected. The win is bursts and retries, and the analysis switch can stay off if it doesn't pay.

## Migration Plan

1. Merge the accounting fix and the assistant cache points, with the analysis switch off by default, into `local` once the tests pass.
2. With Jayson's OK, run the measurement script once and record the results.
3. Deploy, passing `-c novaCacheAnalysis=true` only if the image check passed.
4. Rollback: redeploy with `novaCacheAnalysis=false`. For the assistant, revert the commit. Accounting needs no rollback.

## Test strategy

- **Unit (pytest), usage module (`test_usage.py`):**
  - `Tokens.from_converse` and `price` against every `llm-usage-tracking` cost scenario.
  - `UsageRecorder` against a moto DynamoDB table. Cover first call, two sources adding up, the Toronto day boundary using a fixed clock, keying by account, and a write failure that only warns (a fake table that raises).
- **Unit (pytest):**
  - `cost_usd` with cache counts, using the spec scenarios' exact numbers.
  - `build_request` with `cache` off or on, with and without references: block order, cache point shape, no `ttl`, nothing in `toolConfig`, at most 2 cache points.
  - `NovaAnalyzer.from_env` parsing of `NOVA_CACHE_ANALYSIS` (`true` turns it on; unset or `yes please` leaves it off) and of the cache prices.
  - The usage summary helper in the measurement script.
- **Contract (botocore Stubber / fake client):**
  - Canned Converse responses with and without `cacheReadInputTokens` / `cacheWriteInputTokens`, through `NovaAnalyzer.analyze`. Assert on the `nova_cost` log fields and that the retry request is identical.
  - Through `assistant.run` with the existing in-process MCP server helper (`tests/mcp_helpers.py`) and a scripted fake Bedrock client. Record each request and assert on the cache points by round, and on the `ask_agent` fields.
- **Integration:** `analyze_task` and the Ask route with a moto table and a stubbed Bedrock client. Assert on `llm_usage` events and the `USAGE#<date>` item, check that an over-budget question records nothing, and check that a totals failure leaves the analysis and the answer intact.
- **Infra (Vitest/Jest CDK assertions):** the pipeline Lambda gets `TIME_ZONE`; both Lambdas get `NOVA_PRICE_CACHE_READ` / `NOVA_PRICE_CACHE_WRITE` with the defaults, and the pipeline Lambda gets `NOVA_CACHE_ANALYSIS = "false"`.
- **Fixtures:** extend the existing canned Converse responses under `backend/tests/fixtures/` with cache usage fields. Reuse the existing JPEG fixtures for stills and references.
- **Stubbed:** all Bedrock calls. Nothing hits live AWS. The measurement script is the only live call, run by hand outside the test suite.
