# Design

## Context

The repo has no code yet: CI expects Python projects with a `pyproject.toml` and Node packages with a `test` script. See proposal.md for motivation. The Ring contract comes from Ring's API documentation page and the `AmazonAppDev/ring-api-helloworld` sample; research notes are summarized in the decisions below. Two details are unconfirmed: the Token Exchange request body format, and whether Ring rotates the refresh token on every refresh.

Ring's linking order matters. First Ring POSTs a code to the Token Exchange URL, backend to backend, and that code must be exchanged within 60 s. Later Ring redirects the browser to the Account Link URL with only `nonce` and `time` (epoch ms). Both the nonce and the webhook signature use the same HMAC key from the Ring console: the nonce as base64url without padding, the signature as hex.

## Goals / Non-Goals

**Goals:**
- One `cdk deploy` creates everything; the only manual steps are the Ring console and pasting four values into one secret.
- Every Ring and AWS call is behind an injectable seam, so all spec scenarios run offline.

**Non-Goals:**
- Multiple Ring accounts. The token store holds one account; a new token exchange replaces it.
- Handling motion events beyond handing them to a stub motion handler (that is `door-event-pipeline`).

## Decisions

### Repo layout
- `backend/`: one uv project, package `fridgesense` (src layout), Python 3.13, deps `httpx` and `pydantic`. `boto3` is a dev dependency only, because the Lambda runtime provides it.
- `infra/`: CDK v2 TypeScript app with Vitest and `aws-cdk-lib/assertions`.
- *Alternative:* a uv workspace with one package per Lambda. That's more packaging for no benefit at this size.

### Two Lambdas, one code asset
- `http` handler (`fridgesense.handlers.http.handler`): a tiny router over the HTTP API v2 event for `POST /ring/token`, `GET`/`POST /ring/link` and `POST /ring/webhook`.
- `token_refresh` handler: run every 3 h by an EventBridge schedule.
- Both run on arm64, Python 3.13, with a 10 s timeout and 256 MB of memory.
- *Alternative:* one Lambda per route. That means more cold starts and more CDK, for no isolation benefit with a single user.

### Packaging without Docker
- CDK `Code.fromAsset("../backend")` with local bundling. It runs `uv pip install --target <out> --python-platform aarch64-manylinux2014 --python-version 3.13 --only-binary :all: .`.
- Tests disable bundling with the `aws:cdk:bundling-stacks: []` context, so the Node CI job doesn't need uv.
- *Alternative:* `@aws-cdk/aws-lambda-python-alpha`. It needs Docker and is an alpha module.

### Secrets: config vs tokens
Two Secrets Manager secrets, so code never overwrites what Jayson typed in:

| Secret | Contents | Written by |
| --- | --- | --- |
| `fridgesense/ring-app` | `{"client_id", "client_secret", "hmac_key", "passcode"}` | Jayson, once, with `aws secretsmanager put-secret-value` |
| `fridgesense/ring-tokens` | `{"account_id", "access_token", "refresh_token", "expires_at", "link_status"}` | The Lambdas only |

- `link_status` is one of `unclaimed`, `linked` or `needs_relink`.
- The Lambdas cache config for 5 minutes and always re-read tokens.
- *Alternative:* store tokens in DynamoDB. That's cheaper, but tokens belong with secrets (encryption, audit), and the plan already chose Secrets Manager.

### DynamoDB single table `fridgesense`
- Keys: `pk` and `sk` (strings), with a TTL attribute `ttl`. Billing is on-demand (pay per request).
- This change writes two item types:
  - `pk=ACCOUNT#<account_id>`, `sk=DEVICE#<device_id>`, with `name` and `updated_at`.
  - `pk=ACCOUNT#<account_id>`, `sk=WEBHOOK#<request_id>`, with `ttl` (now + 7 days).
- Dedupe uses `PutItem` with `attribute_not_exists(sk)`; a conditional-check failure means the delivery is a duplicate.
- Replacing the device list queries `begins_with(sk, "DEVICE#")`, deletes devices that are gone, then puts the current ones.
- The table has `RemovalPolicy.RETAIN`, so a `cdk destroy` doesn't drop data by accident.

### Ring client
- A `RingClient` class takes an `httpx.Client` and a `TokenStore`. Requests go to `https://api.amazonvision.com` only.
- It checks token expiry first and refreshes when the access token has less than 5 minutes left. On a 401 it refreshes once and retries once.
- `OAuthClient` posts form-encoded requests to `https://oauth.ring.com/oauth/token`.
- Timeouts are 5 s for the API and 10 s for OAuth.

### Token Exchange body
The handler accepts `code` from a JSON body, a form body or the query string, because the format isn't confirmed. It logs only the field names and content type it received, never the values, so the first real call shows us the format.

### Link page
- Server-rendered HTML from the same Lambda, with no JavaScript and inline CSS.
- The passcode is compared with `hmac.compare_digest`.
- `account_identifier` is a fixed masked string, `o***r@fridgesense.app`.
- *Alternative:* serve it from the PWA. That's not built yet, and this page has to exist first.

### Webhook
- The handler verifies the signature on raw bytes (decoding base64 when the gateway marks the body so), then parses and dedupes, then dispatches.
- The `MotionHandler` protocol's default implementation only logs. `door-event-pipeline` replaces it with "start the Step Functions execution".
- Every signed call gets a 200 within milliseconds.

### Logging
Logs are structured JSON lines through stdlib `logging`. A redaction helper drops any key named `code`, `*token*`, `*secret*`, `passcode` or `hmac_key`.

### Device command
`uv run fridgesense-devices` is a console script. It uses the real secrets and table through the `AWS_PROFILE` loaded from `.env`, and goes through the same `RingClient`.

## Test strategy

| Level | What | How |
| --- | --- | --- |
| Unit (pytest) | Signature check, nonce HMAC, freshness window, redaction, router | Pure functions; nonce test vectors computed in the test from a known key |
| Contract (pytest + respx) | Ring OAuth, `/v1/users/me`, app-integrations POST/PATCH, `/v1/devices` | `respx` mocks `httpx`; tests assert exact URLs, headers, form bodies and JSON bodies |
| Integration (pytest + moto) | HTTP handler end to end: API Gateway v2 events → handler → Secrets Manager + DynamoDB | `moto` `mock_aws` creates both secrets and the table; respx stubs Ring |
| Infra (Vitest) | Synthesized template: routes, schedule rate, runtimes and architecture, secret names, table keys/TTL/retain, IAM grants limited to the two secrets and the table | `Template.fromStack`, with bundling disabled |

**Fixtures** (`backend/tests/fixtures/ring/`), from the recorded shapes in Ring's docs:
- `webhook_motion_detected.json` (v1.1 with `meta.account_id`)
- `webhook_app_integration_added.json`
- `webhook_button_press.json`
- `oauth_token.json`
- `oauth_refresh.json`
- `users_me.json`
- `devices.json`
- `app_integrations_patch.json`

**Clock:** handlers take a `now()` callable, so freshness and expiry tests are exact.

Nothing in the tests calls Ring or AWS.

## Risks / Trade-offs

- [The Token Exchange body differs from what we accept] → Accept JSON, form and query; the redacted log of field names shows the real format on the first link attempt; the fix is one line.
- [Refresh-token rotation races between the schedule and a reactive refresh] → One user, low traffic, and the 5-minute pre-expiry refresh makes a reactive refresh rare. If it happens, the account shows `needs_relink` and Jayson re-links in under a minute.
- [Passcode brute force on a public URL] → Use a long random passcode (`openssl rand -base64 24`). For one user and a short demo window, that's enough; there's no lockout logic.
- [Docs say "every 24 h" but access tokens last 4 h] → Refresh every 3 h; that costs about 240 Lambda runs a month, which is free.
- [Linking before the camera arrives] → Linking works with no devices; device discovery stores an empty list, and the device command refreshes it once the camera is set up.

## Migration Plan

1. `cdk deploy` (with Jayson's approval). Outputs give the three URLs.
2. Create the Ring private app in the console and paste in the URLs.
3. `put-secret-value` the Client ID, Client Secret, HMAC key and passcode.
4. Link from the Ring app.

Rollback: `cdk destroy`. The table is retained; delete it by hand if needed.
