# FridgeSense

A Ring Indoor Cam 2K watches your fridge. Each time the door opens, the clip goes to S3 and Amazon Bedrock Nova lists what went in or came out. FridgeSense keeps a running inventory and door open/close statistics, available in a PWA and through an MCP server for Alexa+.

See [docs/hackathon-plan.md](docs/hackathon-plan.md) for the full plan.

## Development

The project is spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec) and built test-first. See [CLAUDE.md](CLAUDE.md) for the workflow.

### Layout

- `backend/`: Python 3.13 package `fridgesense` (Ring client, Lambda handlers, CLI). uv + pytest.
- `infra/`: AWS CDK app in TypeScript. Vitest.
- `openspec/`: specs and changes.

### Run the tests

Prerequisites: [uv](https://docs.astral.sh/uv/) and Node.js 22.

```bash
cd backend && uv sync && uv run pytest && uv run ruff check
```

```bash
cd infra && npm ci && npm test
```

Tests never call Ring or AWS: Ring responses come from `backend/tests/fixtures/`, AWS is mocked with moto.

## Setup: deploy and link a Ring camera

You need an AWS account (us-east-1), a Ring account with a camera and a Ring plan or trial, and a `.env` file at the repo root with `AWS_PROFILE=<your profile>`. Every AWS command below loads that profile first.

### 1. Deploy

The first deploy in an account needs a one-time CDK bootstrap:

```bash
set -a; source .env; set +a; cd infra && npm ci && npx cdk bootstrap
```

Then deploy. Lambda packages are built locally with uv (no Docker):

```bash
set -a; source .env; set +a; cd infra && npx cdk deploy
```

The outputs list three URLs: `TokenExchangeUrl`, `AccountLinkUrl` and `WebhookUrl`.

### 2. Create the Ring private app

1. Register at the [Ring developer console](https://developer.amazon.com/ring/console) and create a **Private** app with the Cameras and Doorbells scope.
2. Paste the three URLs from the deploy outputs into the app.
3. Copy the **Client ID**, **Client Secret** and **webhook signing (HMAC) key**. Ring shows them only once.

### 3. Store the Ring credentials

The deploy created the secret `fridgesense/ring-app` with a random link passcode. Add the three Ring values to it. The values are read without echoing, so they stay out of your shell history:

```bash
set -a; source .env; set +a; read -rs "RING_CLIENT_ID?Client ID: "; echo; read -rs "RING_CLIENT_SECRET?Client Secret: "; echo; read -rs "RING_HMAC_KEY?HMAC key: "; echo; aws secretsmanager get-secret-value --secret-id fridgesense/ring-app --query SecretString --output text | jq --arg id "$RING_CLIENT_ID" --arg secret "$RING_CLIENT_SECRET" --arg key "$RING_HMAC_KEY" '.client_id=$id | .client_secret=$secret | .hmac_key=$key' | aws secretsmanager put-secret-value --secret-id fridgesense/ring-app --secret-string file:///dev/stdin
```

(`read -rs "VAR?prompt"` is zsh syntax; in bash use `read -rsp "prompt" VAR`.)

Show the link passcode, which you type on the link page in the next step:

```bash
set -a; source .env; set +a; aws secretsmanager get-secret-value --secret-id fridgesense/ring-app --query SecretString --output text | jq -r .passcode
```

### 4. Link the account

Install the app from the Ring app or console. Ring exchanges tokens with FridgeSense in the background, then opens the link page in your browser. Enter the passcode and the page confirms the link and lists your cameras.

Check the link and list the cameras at any time:

```bash
set -a; source .env; set +a; cd backend && uv run fridgesense-devices
```

Ring tokens are refreshed every 3 hours. If a refresh is ever rejected, the logs show `token_refresh_rejected`; link again from the Ring app.

### Remove

```bash
set -a; source .env; set +a; cd infra && npx cdk destroy
```

The DynamoDB table and the `fridgesense/ring-app` secret are kept; delete them in the console if you no longer need them.

## License

MIT — see [LICENSE](LICENSE).
