# Design

## Context

- **Sessions.** `backend/src/fridgesense/session.py` signs each token with a key derived from its role's passcode and the label `fridgesense-session-v1`. Lifetime is `TTL_S = 30 days`. The PWA (`pwa/src/session.ts`) stores only `token` and `role`. It returns to sign-in only when a request gets 401 (`App.tsx` `report`). So an offline or idle app keeps showing data past expiry.
- **Analysis.** `inventory.analyze_task` loads the stills from S3 and calls `NovaAnalyzer.analyze(stills, inventory_names, context)`. That function calls `build_request`, which lays out `Image n of N` + still blocks, then `INSTRUCTIONS`.
- **Storage.**
  - DynamoDB single table: `pk = ACCOUNT#<account_id>`, with sort-key prefixes such as `ITEM#`. `FridgeTable.query(account_id, prefix)` already paginates.
  - The API Lambda and the pipeline Lambda both have read/write access to the table.
  - The only S3 bucket, the stills bucket, expires **every** object after 7 days. Its keys start `accounts/<id>/devices/...`, so a prefix rule cannot spare a sibling folder per account.
- **API.**
  - `handlers/api.py` registers routes with `@route(method, path, write=)`. `write=True` already returns 403 for viewers.
  - The PWA `ApiClient` turns non-2xx responses into `ApiError(status)` and drops the body.
- **Overlap.** The in-progress `voice-page` change adds a 5th bottom tab, the `ask` route and client method, and edits the same `App.tsx`, `AppContext.tsx` and `client.ts`.

## Goals / Non-Goals

**Goals:**

- Re-ask for the passcode after 24 hours, enforced by the server and noticed by the app without a request.
- Reference images and instructions reach Nova on the next door opening after they are saved.
- No new AWS resources, IAM or dependencies.

**Non-Goals:**

- A general settings framework. Config is exactly two things.
- Image processing on the server, such as resizing or format conversion.

## Decisions

### 1. Expiry: 24 h TTL plus a new signing label

`TTL_S = 24 * 3600`, and the key label becomes `fridgesense-session-v2`.

- Shortening the TTL alone would leave already-issued 30-day tokens valid, because `verify` trusts the signed `exp`.
- Bumping the label invalidates every old token at deploy, with no stored deny-list.
- *Alternative:* reject tokens whose `exp - now > 24 h`. That is more code, and it reads oddly.

### 2. The PWA tracks `expires_at` itself

`saveSession` also stores `fridgesense.expires`, the epoch ms parsed from `expires_at`.

- `loadSession` returns `null` and clears storage when that value is missing or in the past. This also covers tokens from older app versions.
- `App` re-checks every 30 s with `setInterval` and on `visibilitychange`, which meets the "within 60 s" scenario. Offline does not matter because the check reads only the clock.
- The 401 path stays as a backstop for clock skew.

### 3. Config is reached from a header gear, as a `config` value of the `Tab` type, but not added to the `TABS` nav list

- The header gets a gear button that links to `#config`. `tabFromHash` accepts `config`, and the header title becomes "Config".
- The bottom nav stays 4 columns, or 5 after `voice-page`.
- *Alternative:* a 6th tab. That is too cramped at phone width, and it would conflict with `voice-page`'s grid change.

### 4. References live in DynamoDB, not S3

- **Items:**
  - `sk = CONFIG#instructions`, holding `{text, updated_at}`.
  - `sk = REF#<created_ms>-<6 hex>`, holding `{annotation, image_b64, created_at}`.
- **Why not S3:**
  - The sort key gives oldest-first order for free.
  - The browser keeps each image ≤ 200 KB, so the base64 form (≤ ~267 KB) fits under the 400 KB item limit.
  - Six of them come to under ~1.6 MB per config read, which is fine for a Lambda response (6 MB) and for paginated queries.
  - This avoids:
    - a new bucket, or a lifecycle rewrite on the stills bucket (all objects expire there);
    - new IAM;
    - presigned-upload CORS through CloudFront.
- *Alternative:* a separate config bucket, which needs new CDK resources, IAM and a presigned-PUT flow. Revisit only if references grow past 6 or past 200 KB.

### 5. New module `analysis_config.py`

It holds the pure functions, with no HTTP.

- `validate_annotation`, `decode_image` (base64 → bytes; JPEG magic `FF D8 FF`; ≤ 200,000 bytes), and `validate_instructions`.
- `load(table, account_id) -> AnalysisConfig(references: list[(annotation, bytes)], instructions: str)`.
- `add_reference` checks the count of 6 first and raises `TooMany`. `delete_reference` returns `False` for an unknown id. `save_instructions`.

Route handlers in `api.py` map these to 200/400/404/409. Error texts come exactly from the spec. The reference `id` in the API is the `encode_id` (urlsafe base64) of the sort key, the same scheme pending ids use.

### 6. The request layout lives in `analysis.build_request`

The signature becomes `build_request(model_id, stills, inventory, references=(), instructions="")`.

- **References** come first: a header text, then a `Reference n: <annotation>` text and an image block for each.
- **Stills** keep their own `MAX_IMAGES = 4` cap and `Image n of N` numbering.
- **Instructions** are inserted as `Owner's instructions: …\n` before the tool line, by splitting `INSTRUCTIONS` into a body and a tail.
- With empty config the output is byte-identical to today's, so the existing request tests stay untouched.

`NovaAnalyzer.analyze` gains an optional `config` argument, and `analyze_task` calls `analysis_config.load` first.

### 7. Resize in the browser: a pure size function plus a thin canvas wrapper

- `fitWithin(w, h, 768)` returns the target size: 4032×3024 → 768×576, and it never upscales.
- `toJpeg(file)` uses `createImageBitmap` and a canvas `toBlob("image/jpeg", 0.8)`. It retries at 0.6 if the result is over 200 KB, then reads the blob as base64.
- The Config screen takes the resizer as a prop (defaulting to `toJpeg`), because jsdom has no canvas.

### 8. `ApiError` carries the server's message

`ApiError` gets an optional `message` read from the JSON `error` field. The Config screen shows it for 400 and 409 responses. Other screens are unaffected.

## Risks / Trade-offs

- **[Nova pays more attention to the references than to the stills, and "sees" a referenced item that isn't there]** → The header says the references are not part of this door opening. Confidence below 0.7 still goes to Review. The owner can delete a reference that misleads.
- **[Input tokens rise per opening]** → The cap of 6 and the 768 px size bound it (~$0.004 more per opening). The existing `nova_cost` log records it.
- **[Owner's instructions are untrusted text in the prompt]** → Only the owner can write them. The tool choice stays forced and the output schema is validated as today, so the worst case is a bad analysis that goes to Review.
- **[DynamoDB images bloat a partition query]** → Every read goes through a `REF#` or `CONFIG#` prefix, so inventory and event queries never read them.
- **[A clock skewed on the device]** → The server TTL is authoritative, and a 401 still signs the user out.
- **[Merge conflict with `voice-page`]** → The same three PWA files change in both. Keep the edits small. Whichever change merges second rebases.

## Migration Plan

1. Merge into `local`. Run `cdk deploy` (Lambda code only; no resource changes expected in `cdk diff`), then deploy the PWA in the same stack.
2. On deploy, every existing session is rejected. The owner and any judges sign in again with the passcodes they already have.
3. **Rollback:** redeploy the previous commit. Tokens issued under v2 then fail under v1 and people sign in again. The `CONFIG#` and `REF#` items are ignored by old code and can stay.

## Test Strategy

- **Unit (pytest, backend):**
  - **`session`:** the 24 h TTL boundary (T + 24 h accepted, + 1 s rejected), a v1-signed token rejected, and the existing passcode-change cases updated from 30 days.
  - **`analysis_config`:** annotation bounds (0, 1, 80, 81, spaces), image decode (bad base64, PNG magic, 200,000 vs 200,001 bytes), instruction trimming and the 1,000/1,001 boundary, the 6-reference cap, delete of an unknown id, oldest-first load, and per-account isolation. Uses moto DynamoDB through the existing conftest table fixture.
  - **`analysis.build_request`:** references before stills with exact labels, reference image blocks as bytes, the still cap independent of references, owner's instructions placed before the tool line, and empty config byte-identical to the current output (the existing tests stay as the regression guard).
- **Contract (pytest, `handlers/api` via `tests/api_helpers.call`):**
  - Each config route's status codes and JSON bodies, as named in the `analysis-config` spec.
  - Viewer 403 on the three writes, 401 without a token, and `expires_at` = now + 24 h on sign-in.
- **Integration (pytest):** `analyze_task` with moto S3 and DynamoDB and a stub analyzer, or a botocore Stubber on `converse`. Saved config appears in the request. After a delete, the next request lacks the reference. Uses the existing `tests/fixtures/nova/converse_tool_use.json` as the canned response.
- **PWA (Vitest + Testing Library):**
  - **`session.ts`:** expiry stored, past or missing expiry cleared.
  - **`App`:** expired on open shows SignIn with no inventory call. Fake timers past `expires_at` return to SignIn within 60 s. The gear opens `#config`.
  - **`Config.tsx`:** uses an injected stub API and a stub resizer. Covers add/delete/limit/disabled states, the instruction counter and save, viewer read-only, and the server error message shown.
  - **`fitWithin`:** dimension cases.
- **Fixtures:** two tiny JPEGs (a few hundred bytes, generated in-test with Pillow, or a committed `tests/fixtures/images/ref-*.jpg`), one PNG header for the negative case, and a 200,001-byte JPEG-magic blob built in-test. No live AWS or Bedrock.
