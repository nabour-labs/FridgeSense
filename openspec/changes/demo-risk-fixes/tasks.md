# Tasks

## 1. CloudFront passes API errors through

- [x] 1.1 Write failing test in `infra/test/site.test.ts` for "Viewer write refused through the CDN" / "Not found through the CDN": the distribution has no `CustomErrorResponses`. Replace the old assertion that expected them, since the spec changes it. Also cover "App shell at the root": `DefaultRootObject` is `index.html`. Verify: `cd infra && npm test` fails on the new assertion.
- [x] 1.2 Remove `errorResponses` from `infra/lib/app-site.ts`. Verify: `cd infra && npm test` is green.

## 2. No door event left analyzing

- [x] 2.1 Write failing test in `infra/test/pipeline.test.ts` for "Save fails": the `Save` state's `Catch` is `[{ErrorEquals: ["States.ALL"], ResultPath: "$.error", Next: "MarkFailed"}]`. Keep the existing Analyze catch assertion for "Analysis fails". Verify: the test fails.
- [x] 2.2 Add `save.addCatch(markFailed, ...)` in `infra/lib/door-pipeline.ts`. Verify: `cd infra && npm test` is green.

## 3. Bounded Bedrock call time

- [x] 3.1 Write failing test for "Client sends one attempt": `pipeline.bedrock_client()` has `total_max_attempts == 1`, `read_timeout == 30` and `connect_timeout == 5`. Verify: `cd backend && uv run pytest -k bedrock_client` fails.
- [x] 3.2 Write failing tests for "Read timeout is retryable": a stub client whose `converse` raises `ReadTimeoutError` or `ConnectTimeoutError` makes `analyze` raise `BedrockRetryable` with code `ReadTimeout` or `ConnectTimeout` and log `nova_error`. Verify: the tests fail.
- [x] 3.3 Implement the client config in `handlers/pipeline.py` and the timeout mapping in `analysis.py`. Verify: `cd backend && uv run pytest` is green.

## 4. Ask screen stops when left

- [x] 4.1 Write failing tests in `pwa/src/screens/Ask.test.tsx` for "Leave while listening" (no `ask` call after unmount, and the recognizer was aborted or stopped) and "Leave while speaking" (`speechSynthesis.cancel` called on unmount). Verify: `cd pwa && npx vitest run src/screens/Ask.test.tsx` fails.
- [x] 4.2 Add the unmount cleanup to `Ask.tsx`. Verify: the Ask tests are green.

## 5. Stale poll responses ignored

- [x] 5.1 Write failing tests in `pwa/src/useLoad.test.tsx` for "Poll in flight during a save" and "Out-of-order polls", using deferred promises. Verify: they fail.
- [x] 5.2 Add the generation counter to `useLoad.ts`. Verify: `cd pwa && npm test` is green, including the Fridge/Review/Config tests.

## 6. Stable still links on Activity

- [x] 6.1 Write failing tests in `pwa/src/screens/Activity.test.tsx` for "Poll with fresh links", "Links refreshed after 10 minutes" and "Still count changes", using fake timers. Verify: they fail.
- [x] 6.2 Implement the still-link cache and key still buttons by index in `Activity.tsx`. Verify: the Activity tests are green.

## 7. Wrap up

- [x] 7.1 Run everything green: `cd backend && uv run pytest && uv run ruff check .`, `cd pwa && npm test && npx tsc --noEmit`, `cd infra && npm test`. Record the results.
