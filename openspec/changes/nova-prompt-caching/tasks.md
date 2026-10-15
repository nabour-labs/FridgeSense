# Tasks

## 1. Shared usage module

- [x] 1.1 Confirm the Nova 2 Lite cache read and cache write prices (us. profile) on the Bedrock pricing page. If they differ from 0.0000825 / 0.00033, update the defaults and the scenario numbers in `specs/` and `design.md` before writing tests. Verify: the prices and their source are noted in `design.md` Decision 2.
- [x] 1.2 Write failing tests in `backend/tests/test_usage.py` for `Tokens.from_converse`, `price` and `Prices.from_env`. Cover "Uncached call" (0.000653), "Cache write" (0.00033), "Usage missing entirely" (all 0, usd 0.0), the 0.000818 cache-read case, and "Cache prices from configuration" (0.0006, with the `NOVA_PRICE_CACHE_*` env set). Verify: `uv run pytest tests/test_usage.py` fails with ImportError or assertion errors.
- [x] 1.3 Implement `Tokens`, `Prices` and `price` in `backend/src/fridgesense/usage.py`, and make `analysis.cost_usd` delegate to `price`. Verify: `uv run pytest tests/test_usage.py tests/test_analysis_response.py` is green.
- [x] 1.4 Write a failing moto test for `FridgeTable.add_many(pk, sk, amounts)`: one call creates the item with every counter, and a second call adds to them. Verify: it fails.
- [x] 1.5 Implement `FridgeTable.add_many` as a single `UpdateItem` with `ADD` on every attribute. Verify: the 1.4 test passes.
- [x] 1.6 Write failing tests in `test_usage.py` for `UsageRecorder`. Cover "First call of the day", "Calls from both sources add up", "Household day boundary" (fixed clock at 2026-10-21T03:30Z gives `USAGE#2026-10-20`), "Totals keyed by account", and that the `llm_usage` event carries the fields of "Analysis call" and no other keys. Add a fake table that raises, for the "llm_usage_store_failed" warning: the recorder doesn't raise and `llm_usage` is still logged. Verify: they fail.
- [x] 1.7 Implement `UsageRecorder`, which logs `llm_usage`, then calls `add_many` with the `usd` as a 6-decimal `Decimal`, and catches and logs any write error. Verify: `uv run pytest tests/test_usage.py` is green.

## 2. Analysis cost and usage tracking

- [x] 2.1 Write failing tests in `test_analysis_response.py`, using canned responses with cache usage added under `backend/tests/fixtures/converse/`. Cover "Cost of one analysis" and "Cost of a retried analysis" (still hold), "No cache fields in usage", "Cache read priced at the cache-read rate" and "Cache write priced at the cache-write rate" on the `nova_cost` fields. Also cover the `on_usage` callback: called once per response ("Retried analysis": twice) and not called on `ThrottlingException` ("Call that raises an error"). Verify: the new tests fail.
- [x] 2.2 Implement it: `analysis.Usage` holds `Tokens`, `analyze` logs the cache counts in `nova_cost` and calls `on_usage`, and `NovaAnalyzer.from_env` uses `Prices.from_env`. Verify: `uv run pytest tests/test_analysis_response.py tests/test_analysis_request.py` is green.
- [x] 2.3 Write failing integration tests in `test_analyze_task.py` with a moto table and a stubbed Bedrock client. Cover "Analysis call": an `llm_usage` event with `source = "analysis"`, and `USAGE#<date>` updated alongside `nova_usd`. Cover "DynamoDB error during analysis": the totals write fails, the inventory and `nova_usd` are still saved, and a warning is logged. Verify: they fail.
- [x] 2.4 Implement it: `analyze_task` builds a `UsageRecorder(source="analysis")` from the account, the table and `TIME_ZONE`, and passes it as `on_usage`. Verify: `uv run pytest tests/test_analyze_task.py tests/test_pipeline_e2e.py` is green.

## 3. Assistant cost and usage tracking

- [x] 3.1 Write failing tests in `test_assistant_loop.py` / `test_assistant_failures.py`. Cover "Second round read from cache" (usd 0.000787, cache_read_tokens 1200) and "No cache fields" (zeros) on `ask_agent`. Cover "Assistant rounds": `on_usage` is called once per model call, including the first round of a question whose second call fails. Check that "Answered question" and "Failed question still logs cost" still pass. Verify: the new tests fail.
- [x] 3.2 Implement it: `_Run.spend` takes `Tokens` and prices them with `usage.price`, `run()` takes `prices: Prices` and `on_usage`, and `ask_agent` logs both cache counts. Verify: `uv run pytest tests/test_assistant_loop.py tests/test_assistant_failures.py` is green.
- [x] 3.3 Write failing tests in `test_api_ask.py` with a moto table and a fake Bedrock client. Cover "Assistant rounds" end to end (two `llm_usage` events with `source = "assistant"`, and `assistant_calls = 2` on today's usage item). Cover "No content in the log" (no `llm_usage` record contains `milk`, the system prompt or a tool result), "DynamoDB error during a question" (the answer is still returned with `outcome = "answered"`) and "Over-budget question records nothing". Verify: they fail.
- [x] 3.4 Implement it: `_ask_assistant` builds `Prices.from_env()` and a `UsageRecorder(source="assistant")` and passes both to `assistant.run`. Verify: `uv run pytest tests/test_api_ask.py tests/test_ask_budget.py` is green.

## 4. Assistant cache points

- [x] 4.1 Write failing tests in `test_assistant_loop.py` that record each Converse request from the fake Bedrock client. Cover "First round" (system ends with a cachePoint, the question has none, tools have none), "Tool results end with a cache point", "Earlier cache points stay in place" (exactly 4 cache points on round 4) and "Cache points carry no ttl". Verify: they fail.
- [x] 4.2 Implement the cache points in `assistant._loop`: a `CACHE_POINT = {"cachePoint": {"type": "default"}}` constant, appended to `system` and to each tool-results message before it goes into `messages`. Verify: the 4.1 tests and the whole `tests/test_assistant_*.py` set are green.

## 5. Opt-in analysis cache points

- [x] 5.1 Write failing tests in `backend/tests/test_analysis_request.py` for "Caching off by default" (equal to today's request, no `cachePoint` anywhere), "Caching on with references", "Caching on without references", and "Cache point shape and placement limits" (no `ttl`, `toolConfig.tools == [TOOL_SPEC]`, ≤2 cache points). Verify: they fail.
- [x] 5.2 Implement the `cache: bool = False` argument on `build_request`, which inserts the cache points after the last reference and after the last still. Verify: `uv run pytest tests/test_analysis_request.py tests/test_analysis_config.py` is green, with the existing "No config" and "References before stills" scenarios unchanged.
- [x] 5.3 Write failing tests for `NovaAnalyzer.from_env` reading `NOVA_CACHE_ANALYSIS` (`true` turns it on; unset or "Unrecognized setting value" `yes please` leaves it off). Also cover "Retry sends the same cached request": two identical recorded requests with cache points. Verify: they fail.
- [x] 5.4 Implement it: `NovaAnalyzer` takes `cache_analysis`, `from_env` parses it, and `analyze` passes it to `build_request`. Verify: `uv run pytest tests/test_analysis_request.py tests/test_analysis_response.py` is green.

## 6. Infra wiring

- [x] 6.1 Write failing CDK tests in `infra/test/site.test.ts`, `pipeline.test.ts` and `stack.test.ts`: the pipeline Lambda gets `TIME_ZONE` (same value as the app-site Lambda), both Lambdas get `NOVA_PRICE_CACHE_READ = "0.0000825"` and `NOVA_PRICE_CACHE_WRITE = "0"`, the pipeline Lambda gets `NOVA_CACHE_ANALYSIS = "false"`, and `-c novaCacheAnalysis=true` gives `"true"`. Verify: `npm test` in `infra/` fails on these.
- [x] 6.2 Implement the context values `novaPriceCacheRead`, `novaPriceCacheWrite` and `novaCacheAnalysis` in `fridgesense-stack.ts`, with props and env in `app-site.ts` and `door-pipeline.ts`, and pass `timeZone` to the pipeline. Verify: `npm test` in `infra/` is green.

## 7. Measurement script

- [x] 7.1 Write a failing unit test `backend/tests/test_measure_prompt_cache.py` for the pure `summarize(usage, metrics)` helper, which returns input, cache read, cache write, output and latency. Absent fields count as 0. Verify: it fails.
- [x] 7.2 Implement `backend/scripts/measure_prompt_cache.py`. It refuses to run without `--yes`, and the cases it sends are set out in Decision 5 of `design.md`. Verify: the 7.1 test passes and `uv run python scripts/measure_prompt_cache.py` without `--yes` exits non-zero without calling Bedrock.
- [x] 7.3 Ask Jayson's OK, then run the script once with `set -a; source .env; set +a`. Record the output and the pass/fail against Decision 5's criteria in `openspec/changes/nova-prompt-caching/measurement.md`, and add a friction-log entry if Nova misbehaves. If the assistant check fails, fall back to a system-only cache point (update the spec first). Verify: `measurement.md` exists, with a recommendation for `novaCacheAnalysis`.

## 8. Wrap-up

- [x] 8.1 Run the full suites and linters: `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`, `cd infra && npm test`, `cd pwa && npm test`. Verify: all green, and report the commands and results.
