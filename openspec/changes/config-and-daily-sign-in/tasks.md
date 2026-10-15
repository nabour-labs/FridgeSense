# Tasks

## 1. 24-hour session tokens (inventory-api)

- [x] 1.1 Write failing tests in `tests/test_session.py` for "Token one day old" (T + 24 h accepted, T + 24 h + 1 s rejected) and "Token from before the change" (a token signed with the `fridgesense-session-v1` label and a future `exp` is rejected), and update the existing `TTL_S == 30 days` assertion to 24 h; run `uv run pytest tests/test_session.py` and verify they fail on the TTL and label
- [x] 1.2 Set `TTL_S = 24 * 3600` and the key label to `fridgesense-session-v2` in `session.py`; verify 1.1 passes
- [x] 1.3 Update `tests/test_api_auth.py` "Correct passcode" and "Demo passcode" to expect `expires_at` = now + 24 h, add an API-level "Token one day old" test (`GET /api/inventory` at the boundary gives 200 then 401 `{"error": "sign in"}`), and verify `uv run pytest tests/test_api_auth.py tests/test_session.py` is green

## 2. Sign-in expiry in the PWA (inventory-app)

- [x] 2.1 Write failing Vitest tests in `src/session.test.ts`: `saveSession` stores `expires_at`; `loadSession` returns null and clears storage for a past expiry ("Opened after 24 hours") and for a token with no stored expiry ("Token stored without expiry"); run `npm test -- session` and verify they fail
- [x] 2.2 Add `expiresAt` to `StoredSession` and `saveSession`/`loadSession`/`clearSession` in `session.ts`, and pass `expires_at` from `onSignedIn` in `App.tsx`; verify 2.1 passes
- [x] 2.3 Write failing tests in `App.test.tsx` for "Opened after 24 hours" (SignIn shown, no inventory call) and "Expires while open" (fake timers past `expires_at` → SignIn within 60 s with fetch failing as offline); verify they fail
- [x] 2.4 Add the 30 s interval and `visibilitychange` expiry check in `App.tsx`; verify 2.3 and the existing "Session expired" 401 test pass

## 3. Config storage and validation (analysis-config)

- [x] 3.1 Write failing tests in `tests/test_analysis_config.py` for the validators: annotation bounds (empty, spaces, 1, 80, 81 chars), image decode (bad base64, PNG magic, exactly 200,000 vs 200,001 bytes with JPEG magic) and instructions (trim, "" clears, 1,000 vs 1,001, non-string); run `uv run pytest tests/test_analysis_config.py` and verify they fail because the module is missing
- [x] 3.2 Implement `validate_annotation`, `decode_image` and `validate_instructions` in `fridgesense/analysis_config.py`; verify 3.1 passes
- [x] 3.3 Write failing moto-DynamoDB tests for `add_reference`/`delete_reference`/`save_instructions`/`load`: oldest-first order, "Seventh reference" raises `TooMany` with 6 kept, unknown id returns False, "Config kept per account", "Nothing configured" gives empty config; verify they fail
- [x] 3.4 Implement the storage functions with `CONFIG#instructions` and `REF#<created_ms>-<hex>` items; verify 3.3 passes and `uv run ruff check src tests` is clean

## 4. Config HTTP routes (analysis-config)

- [x] 4.1 Write failing contract tests in `tests/test_api_config.py` for "Config with references" (viewer read), "Nothing configured", "Save instructions", "Clear instructions", "Instructions too long or wrong type", "Add a reference", "Bad annotation", "Not a JPEG or too large", "Seventh reference" (409), "Delete a reference", "Unknown reference" (404), "Viewer cannot change config" (403 on all three writes) and "No token" (401); run them and verify they fail with 404 for the unknown routes
- [x] 4.2 Add `GET /api/config`, `PUT /api/config/instructions`, `POST /api/config/references` and `DELETE /api/config/references/{id}` (writes with `write=True`, ids via `encode_id`) in `handlers/api.py`, with error bodies exactly as specified; verify 4.1 passes
- [x] 4.3 Refactor shared "return full config" code with tests green; run `uv run pytest` for the whole backend

## 5. Config in the Nova request (fridge-change-analysis)

- [ ] 5.1 Write failing tests in `tests/test_analysis_request.py` for "References before stills", "Reference images as bytes" (still cap of 4 independent of references), "Custom instructions in the final text" and "No config" (byte-identical to a request built without config); run and verify they fail on the new `build_request` arguments
- [ ] 5.2 Extend `build_request` and `NovaAnalyzer.analyze` with optional references and instructions (split `INSTRUCTIONS` into body and tool line); verify 5.1 and the existing "Request built from stills and inventory", "Empty inventory" and "Stills sent as bytes" tests pass unchanged
- [ ] 5.3 Write failing tests in `tests/test_analyze_task.py` with moto S3 and DynamoDB plus a botocore Stubber on `converse` (canned `tests/fixtures/nova/converse_tool_use.json`): saved config reaches the request, and "Config changed between openings" (a deleted reference is absent next time); verify they fail
- [ ] 5.4 Make `inventory.analyze_task` call `analysis_config.load` and pass it to the analyzer; verify 5.3 passes and `tests/test_pipeline_e2e.py` is still green

## 6. Config screen in the PWA (inventory-app)

- [ ] 6.1 Write failing tests in `src/api/client.test.ts` for `config()`, `saveInstructions()`, `addReference()`, `deleteReference()` (method, path, body) and for `ApiError` carrying the server's `error` text on 400/409; run `npm test -- client` and verify they fail
- [ ] 6.2 Add the `Config`/`Reference` types, the four client methods, the `ApiError` message, and extend the `Api` pick in `AppContext.tsx`; verify 6.1 passes
- [ ] 6.3 Write failing tests in `src/image.test.ts` for `fitWithin` (4032×3024 → 768×576, portrait, already small stays the same); then implement `fitWithin` and the canvas `toJpeg` wrapper (quality 0.8, retry 0.6 over 200 KB) in `src/image.ts` and verify they pass
- [ ] 6.4 Write failing tests in `App.test.tsx` and `screens/Config.test.tsx` for "Open config" (gear → `#config`, title "Config", `GET /api/config`) and "Viewer sees read-only config"; verify they fail
- [ ] 6.5 Add the `config` tab value, header gear button and `screens/Config.tsx` shell with both sub-sections and viewer read-only rendering; verify 6.4 passes
- [ ] 6.6 Write failing tests in `Config.test.tsx` with a stub resizer for "Add a reference", "Annotation required", "Limit reached", "Delete a reference" (after confirm) and "Upload refused" (server message shown, list unchanged); verify they fail
- [ ] 6.7 Implement the reference list, add sheet (file input with `accept="image/*"` and `capture`, annotation field) and delete confirm; verify 6.6 passes
- [ ] 6.8 Write failing tests for "Save instructions", "Over the limit" and "Unchanged text"; then implement the text area, "n / 1000" counter, Save and "Saved" notice and verify they pass
- [ ] 6.9 Check the Config screen at phone width in light and dark mode in the dev preview, and fix any layout issues found

## 7. Integration and wrap-up

- [ ] 7.1 Run `cd infra && npx cdk synth` and `cdk diff` (no deploy) and verify there are no resource changes beyond Lambda code and PWA assets
- [ ] 7.2 Update `README.md` (Config screen, daily sign-in) and add any Bedrock/AWS friction hit during the work to `docs/friction-log.md`
- [ ] 7.3 Run the full suites green: `cd backend && uv run pytest && uv run ruff check src tests`, `cd pwa && npm test && npm run lint` (if present), `cd infra && npm test`; report the commands and results
