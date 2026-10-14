# Tasks

## 1. Project scaffolding

- [x] 1.1 Create `backend/` uv project (package `fridgesense`, src layout, Python 3.13; deps httpx, pydantic; dev deps pytest, respx, moto[secretsmanager,dynamodb], boto3, ruff) with a `fridgesense-devices` console script; verify `cd backend && uv run pytest` runs (0 tests) and `uv run ruff check` passes
- [x] 1.2 Add Ring fixtures under `backend/tests/fixtures/ring/` (motion, app_integration_added, button_press webhooks; oauth token and refresh; users_me; devices; app_integrations_patch) from the documented shapes; verify each file parses as JSON in a fixture-loading test
- [x] 1.3 Create `infra/` CDK v2 TypeScript app with Vitest (`npm test` = `vitest run`) and an empty `FridgeSenseStack`; verify `npm test` passes and `npx cdk synth` runs with bundling disabled

## 2. Crypto helpers and logging

- [x] 2.1 Write failing tests for webhook scenarios "Valid signature", "Invalid signature", "Missing signature header" at the function level (`verify_signature(raw_body, header, key)`); verify they fail on import
- [x] 2.2 Implement `verify_signature` (constant-time, `sha256=` hex) to make the tests pass
- [x] 2.3 Write failing tests for "Stale link request", "Time in the future", "Nonce does not match" at the function level (`nonce_for`, `is_fresh`), with a test vector computed from a known key; verify they fail
- [x] 2.4 Implement `nonce_for` (base64url, no padding) and `is_fresh` (600 s window, rejects the future) to make the tests pass
- [x] 2.5 Write failing tests for "Secrets never logged": the redaction helper drops `code`, `access_token`, `refresh_token`, `client_secret`, `passcode`, `hmac_key` at any depth; then implement it and verify it passes

## 3. Config and token store

- [x] 3.1 Write failing moto tests for reading `fridgesense/ring-app` (with 5-minute cache) and for reading and writing `fridgesense/ring-tokens` (empty store returns None; save then load round-trips all five fields); verify they fail
- [x] 3.2 Implement `AppConfig` loader and `TokenStore` on Secrets Manager to make the tests pass

## 4. OAuth and Ring client

- [x] 4.1 Write failing respx tests for `OAuthClient.exchange_code` and `OAuthClient.refresh` asserting the exact URL, form body (`grant_type`, `code` / `refresh_token`, `client_id`, `client_secret`) and parsed response; verify they fail
- [x] 4.2 Implement `OAuthClient` to make the tests pass
- [x] 4.3 Write failing tests for token-lifecycle scenarios "Token about to expire", "Ring answers 401 once", "Ring answers 401 after refresh", "Bearer header"; verify they fail
- [x] 4.4 Implement `RingClient` (pre-expiry refresh, one refresh-and-retry on 401, base URL locked to api.amazonvision.com) to make the tests pass
- [x] 4.5 Write failing tests for scheduled-refresh scenarios "Refresh succeeds and rotates the refresh token", "Refresh response without a new refresh token", "Nothing to refresh", "Refresh token rejected", "OAuth endpoint unavailable"; verify they fail
- [x] 4.6 Implement the `token_refresh` handler to make the tests pass

## 5. Token exchange endpoint

- [x] 5.1 Write failing handler tests (API Gateway v2 events, moto, respx) for "Valid authorization code", "Code sent as a form field or query parameter", "Missing code", "Ring rejects the code", "Secrets never logged" (using caplog); verify they fail
- [x] 5.2 Implement the HTTP router and `POST /ring/token` to make the tests pass

## 6. Account link page

- [x] 6.1 Write failing handler tests for "Ring opens the link page", "Link page opened without Ring parameters", "Wrong passcode"; verify they fail
- [x] 6.2 Implement `GET`/`POST /ring/link` form rendering and the passcode check to make the tests pass
- [x] 6.3 Write failing handler tests for "Stale link request", "Time in the future", "Nonce does not match", "No unclaimed account", "Successful link" (asserting the exact POST and PATCH bodies), "Ring rejects the integration"; verify they fail
- [x] 6.4 Implement nonce matching and the app-integrations POST and PATCH to make the tests pass

## 7. Device discovery

- [ ] 7.1 Write failing tests for "One camera returned", "Device removed since last link", "Device list unavailable" (link flow plus DynamoDB); verify they fail
- [ ] 7.2 Implement `DeviceRepository` (replace the account's device list) and call it after a successful link to make the tests pass
- [ ] 7.3 Write failing tests for "Listing devices from the command line" and "No linked account" (capsys, exit codes); verify they fail
- [ ] 7.4 Implement the `fridgesense-devices` command to make the tests pass

## 8. Webhook intake

- [ ] 8.1 Write failing handler tests for "Valid signature", "Invalid signature", "Missing signature header", "Base64-encoded body from the gateway", "Signing key not configured"; verify they fail
- [ ] 8.2 Implement `POST /ring/webhook` signature gating to make the tests pass
- [ ] 8.3 Write failing tests for "First delivery", "Repeated delivery" (DynamoDB conditional put, 7-day TTL), "Unknown event type", "Malformed JSON with a valid signature", "Motion event handed over", "App integration added"; verify they fail
- [ ] 8.4 Implement dedupe, dispatch and the logging `MotionHandler` to make the tests pass

## 9. Infrastructure

- [ ] 9.1 Write failing Vitest assertions: HTTP API routes `POST /ring/token`, `GET /ring/link`, `POST /ring/link`, `POST /ring/webhook`; two Python 3.13 arm64 Lambdas; an EventBridge rule `rate(3 hours)`; secrets `fridgesense/ring-app` and `fridgesense/ring-tokens`; table with `pk`/`sk`, TTL `ttl`, on-demand billing, retain policy; outputs for the three URLs; verify they fail
- [ ] 9.2 Implement the stack (with local uv bundling) to make the tests pass
- [ ] 9.3 Write a failing assertion that the Lambda role can read `ring-app`, read and write only `ring-tokens`, and read and write only the table; then scope the grants and verify it passes

## 10. Docs and final check

- [ ] 10.1 Add README setup steps (prerequisites, `cdk bootstrap`, `cdk deploy`, Ring console URLs, `put-secret-value` command with placeholder values, linking, `fridgesense-devices`); verify each command matches the code
- [ ] 10.2 Run `cd backend && uv run pytest && uv run ruff check && uv run ruff format --check` and `cd infra && npm test`; all green
