# Prompt caching measurement

Run once on 2026-10-15 with Jayson's OK, using the `.env` profile in us-east-1 and model `us.amazon.nova-2-lite-v1:0`:

```bash
set -a; source .env; set +a
cd backend && uv run python scripts/measure_prompt_cache.py --yes
```

## Requests

- **Analysis:** `build_request(..., cache=True)` with 2 references (640×480 JPEGs) and 4 stills (1280×720 JPEGs). Cache points go right after the last reference image and right after the last still. Sent twice.
- **Assistant:** a second-round request: `system` = [prompt, cachePoint], then the question, a `toolUse` turn, and a user message of [`toolResult`, cachePoint]. Sent twice.

## Output

```
model: us.amazon.nova-2-lite-v1:0
analysis #1: ValidationException: ... Malformed input request: #/messages/0/content/4: extraneous key [cachePoint] is not permitted, please reformat your input and try again.
analysis #2: ValidationException: ... (same)
assistant #1: ValidationException: ... Malformed input request: #/messages/2/content/0: extraneous key [cachePoint] is not permitted, please reformat your input and try again.
assistant #2: ValidationException: ... (same)
analysis image prefix cached: FAIL
assistant tool-result cache point: FAIL
```

No call returned usage, so no tokens were billed. Every request was rejected during validation.

## Findings

- botocore's Converse model accepts a `cachePoint` block anywhere in `content`, but Bedrock seems to fold it into the **preceding** content block when it builds Nova's native request (the InvokeModel shape `{"text": ..., "cachePoint": {...}}`).
- Nova 2 Lite rejects that key on an `image` block (analysis, `content/4` is the second reference image) and on a `toolResult` block (assistant, `content/0`). It's likely accepted only after a `text` block, which fits the docs' note that Nova caching is "primarily for text prompts". That last point is untested.
- The `system` cache point wasn't tested on its own, because each request failed on its message cache point first.

## Pass / fail against Design Decision 5

| Check | Result |
| --- | --- |
| Second analysis call reads from cache | **FAIL** (ValidationException) |
| Second assistant call reads from cache | **FAIL** (ValidationException) |
| No call raises ValidationException | **FAIL** |

## Recommendation

- **`novaCacheAnalysis`: keep `false`.** With the current placement (right after an image), turning it on would make every analysis fail with `ValidationException`, so every door opening would end `analysis_failed`. Don't turn it on unless the cache point is moved after a text block and a new measurement passes.
- **Assistant: fall back to a system-only cache point**, as task 7.3 says. Spec and code are updated in this change. The system cache point still needs one live check before deploy, because it's untested.
- A follow-up measurement, with Jayson's OK, could try cache points after a short text block: an "End of reference images." text after the references, and a text block after the tool results. That would show whether image and tool-result prefixes can be cached at all.

## Second run: system-only assistant cache point

Run once more on 2026-10-15 with Jayson's OK, same command and model, after the assistant was changed to cache only the system block (the tool-result message carries no cache point).

```
model: us.amazon.nova-2-lite-v1:0
analysis #1: ValidationException: ... #/messages/0/content/4: extraneous key [cachePoint] is not permitted ...
analysis #2: ValidationException: ... (same)
assistant #1: {'input': 364, 'cache_read': 0, 'cache_write': 766, 'output': 13, 'latency_ms': 717, 'usd': 0.000156}
assistant #2: {'input': 364, 'cache_read': 766, 'cache_write': 0, 'output': 13, 'latency_ms': 1055, 'usd': 0.000219}
analysis image prefix cached: FAIL
assistant system cache point: PASS
```

### Findings

- **The system cache point works.** The first call wrote 766 tokens (2 tool specs plus the system prompt) and the second read all 766 back. There was no `ValidationException`.
- **The prefix cached at 766 tokens**, below the "1K" minimum the guide gives for Nova. The real minimum seems to be lower. With the real six MCP tools, the prefix will be bigger than in this script's two-tool request.
- **Cost:** cache writes are free and aren't billed as input, so the first call (the write) was the cheaper of the two: $0.000156 against $0.000219. Without caching, every call would pay the 766 tokens at the input rate, $0.000253. With caching, the first call pays $0 for them and each later call within 5 minutes pays $0.000063. The saving is about 75% on that prefix for each call after the first.
- **Latency:** 717 ms uncached against 1055 ms with the cache read. One sample on a short prompt is noise; at a few hundred tokens, caching can't save much time. Don't count on a latency gain at this prompt size; the benefit here is cost.
- The analysis case still fails as built, as expected, and was rejected at no cost.

### Updated recommendation

- **Assistant: ship the system-only cache point.** It's accepted and it caches.
- **`novaCacheAnalysis`: keep `false`.** Unchanged from the first run.
