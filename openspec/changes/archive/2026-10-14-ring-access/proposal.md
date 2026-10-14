# Proposal

## Why

Every other piece of FridgeSense (the door-event pipeline, the PWA and the MCP server) needs a working, long-lived connection to the Ring API. Playground tokens expire after about 30 minutes, so the app needs its own private Ring app with account linking, stored tokens and automatic refresh before any real door opening can be analyzed. The camera hasn't arrived yet, so this is the right time to build it: none of it needs footage.

Tracks: **Ring** (the code must call Ring APIs at runtime) and **AWS Builder** (serverless infrastructure in CDK).

## What Changes

- A Python backend project (`backend/`, uv + pytest) with a small Ring API client: authorized requests, token refresh and listing devices.
- Three public HTTPS endpoints the Ring private app requires, behind API Gateway HTTP API → Lambda:
  - **Token Exchange URL**: Ring POSTs an authorization code here; the backend exchanges it with `oauth.ring.com` within 60 s, looks up the Ring `account_id` and stores the tokens as *unclaimed*.
  - **Account Link URL**: Ring sends the browser here with `nonce` and `time`. The page asks for the single passcode, matches the nonce against the unclaimed account (HMAC), then registers and completes the app integration with Ring.
  - **Webhook URL**: accepts Ring's calls, verifies `X-Signature`, skips repeats by `meta.request_id`, and replies 200. Motion events go to a stub handler that `door-event-pipeline` replaces.
- Ring access and refresh tokens stored in Secrets Manager, refreshed by a scheduled Lambda before they expire (about every 3 hours).
- A CDK app (`infra/`, TypeScript, Vitest) that deploys the endpoints, two secrets (app config and tokens), the scheduled refresh and the DynamoDB single table, with snapshot-free assertion tests on the synthesized template.
- Setup steps in the README: Ring developer console, the three URLs, secrets, `cdk deploy`.

## Capabilities

### New Capabilities

- `ring-account-link`: linking the single user's Ring account to FridgeSense, including the passcode-protected link page and the token exchange.
- `ring-token-lifecycle`: storing Ring tokens and keeping them valid with scheduled refresh.
- `ring-webhook-intake`: receiving Ring webhook calls, verifying their signature and acknowledging them safely.
- `ring-device-discovery`: listing the linked account's Ring devices so the app knows which camera to watch, plus a command-line listing for setup.

### Modified Capabilities

None (no existing specs).

## Out of scope

- Processing motion events, downloading stills, Nova analysis (`door-event-pipeline`).
- Lifecycle webhooks (`app_integration_removed`, `device_removed`, `subscription_deactivated`) and subscription checks.
- Cognito or any multi-user sign-in; there is one user and one passcode.
- Live video (WHEP) sessions.
- CI-driven deploys; `cdk deploy` is run by hand from the Mac.

## Impact

- New code: `backend/` (Python 3.13, httpx, pydantic; boto3 from the Lambda runtime) and `infra/` (CDK v2, TypeScript).
- New AWS resources in us-east-1: HTTP API, 3–4 Lambdas, one Secrets Manager secret, one EventBridge schedule, one DynamoDB table. Expected cost while idle: under $1/month (the secret is about $0.40/month).
- CI: the existing `unit-tests` workflow picks up `backend/pyproject.toml` and `infra/package.json` automatically.
- Manual steps for Jayson: register the Ring private app, paste the three URLs from `cdk deploy` output, put the Client ID, Client Secret and webhook signing key into the secret.
