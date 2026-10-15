# Design

## Context

See proposal.md for why. The relevant facts in the current code:

- `infra/lib/app-site.ts` sets distribution-wide `errorResponses` for 403 and 404. CloudFront custom error responses apply to every origin, including the `/api/*` HTTP API behaviour. The PWA routes by `location.hash` (`App.tsx`), so the browser only ever asks for `/` and real asset paths.
- `infra/lib/door-pipeline.ts`: only Analyze has `addCatch(markFailed)`. `fetch_stills` writes the door event (`analyzing`) as its last action, inside the claim transaction, so a FetchStills failure never leaves an event behind. Save runs after the event exists and has no catch.
- `handlers/pipeline.py` builds Bedrock with `retries={"max_attempts": 1}`. In botocore that means one *retry* (2 HTTP attempts), each up to `read_timeout=60`, and `NovaAnalyzer` makes up to 2 requests, so the worst case is about 240 s against a 90 s Lambda timeout. `analysis.py` only catches `ClientError`, so a `ReadTimeoutError` escapes untyped.
- `useLoad` calls `setData` with every poll result, and screens call the returned `setData` after mutations.
- `Ask.tsx` keeps the recognizer in a ref and has no unmount cleanup. `App.tsx` remounts the screen per tab (`<main key={tab}>`).
- The API presigns stills on every request (15 min TTL), so each poll returns new URLs. `Activity.tsx` keys still buttons by URL.

## Goals / Non-Goals

**Goals:** the smallest change to each spot that meets the spec deltas, with tests at the level where the defect lives.

**Non-Goals:** changing the API's presigning, adding a catch to FetchStills, or the other review findings listed as out of scope in the proposal.

## Decisions

1. **Drop `errorResponses` instead of adding a CloudFront Function.** Hash routing means no deep-link paths exist, so no fallback is needed. The alternative (a viewer-request function on the default behaviour that rewrites extensionless paths) adds code and a resource for no benefit.
2. **Save catches to MarkFailed.** `save.addCatch(markFailed, { errors: ["States.ALL"], resultPath: "$.error" })`, the same shape as Analyze. `mark_failed_task` already sets `analysis_failed` and logs the error name. FetchStills gets no catch, because its only write is the final transaction.
   - `save_task` applies changes item by item before marking the event done, so a mid-save failure could leave a partial apply. Accepted for the MVP. A retry would double-apply, which is worse.
3. **Bedrock client: `Config(retries={"total_max_attempts": 1, "mode": "standard"}, connect_timeout=5, read_timeout=30)`.** That gives 2 × (5 + 30) = 70 s worst case, plus S3 reads, within 90 s. In `NovaAnalyzer.analyze`, catch `botocore.exceptions.ReadTimeoutError` and `ConnectTimeoutError` and raise `BedrockRetryable("ReadTimeout" | "ConnectTimeout")`. The state machine's existing `BedrockRetryable` retry then applies.
4. **`useLoad` generation counter.** A `useRef` counter. Each `load()` takes `gen = ++ref.current` and drops its result (success or failure) if `ref.current !== gen` when it settles. The returned `setData` is wrapped to bump the counter first. This handles both in-flight polls during a save and out-of-order polls, with no change to the hook's API.
5. **Stable stills in Activity, client side.** A `useRef<Map<eventId, {stills, at}>>` in Activity. When events arrive, each event's `stills` are replaced by the cached ones if the count matches and `now - at < 10 min`; otherwise the cache is updated. Still buttons are keyed by index. The alternative was fixed-window presigning on the backend, but botocore signs with the current time and the Lambda's session credentials rotate, so the URLs would still change.
6. **Ask unmount cleanup.** `useEffect(() => () => { const r = recognizer.current; recognizer.current = null; r?.abort?.() ?? r?.stop(); speechSynthesis?.cancel(); }, [])`. Clearing the ref first makes the existing `onend` guard (`recognizer.current !== rec`) drop the transcript. Add optional `abort()` to the `Recognizer` type.

## Risks / Trade-offs

- [A Nova answer slower than 30 s now times out] → The workflow retries it. Nova Lite with 4–8 images usually answers in 3–15 s.
- [Partial apply if Save fails mid-way] → The event is marked `analysis_failed` so it is visible. Rare.
- [Stills shown from cache whose links expire at 15 min] → The cache is refreshed after 10 min, leaving a 5 min margin.

## Migration Plan

Merge, then `cdk deploy` (needs Jayson's OK). Rollback is reverting the commit and redeploying. There is no data change.

## Test strategy

- **Infra (Vitest, synth with bundling off):**
  - The distribution has no `CustomErrorResponses`, and `DefaultRootObject` is still `index.html`.
  - The `Save` state has a `States.ALL` catch to `MarkFailed` with `ResultPath: "$.error"`.
- **Backend (pytest):**
  - `pipeline.bedrock_client()` config has `total_max_attempts == 1`, `read_timeout == 30` and `connect_timeout == 5`.
  - A fake Bedrock client raising `ReadTimeoutError` / `ConnectTimeoutError` makes `NovaAnalyzer.analyze` raise `BedrockRetryable` with the right code. Stub client, no network.
- **PWA (Vitest + Testing Library, fake API in `test-utils`):**
  - `useLoad`: deferred promises to drive (a) a poll resolving after `setData`, and (b) two polls resolving out of order.
  - Ask: a fake `SpeechRecognition` class. Start listening, unmount (switch tab), fire `onresult` + `onend`, and assert no `ask` call and that `abort`/`stop` was called. Assert a `speechSynthesis.cancel` spy is called on unmount.
  - Activity: fake timers. First poll returns `a1..a4`, next poll `b1..b4` → images still `a1..a4`. Advance past 10 min → next poll `c1..c4` shows. A count change shows the new links.
