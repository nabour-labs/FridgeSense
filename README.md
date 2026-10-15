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

### 5. What happens on a door opening

1. Ring sends a motion webhook. FridgeSense starts one Step Functions run (`fridgesense-door-events`) for it.
2. The run waits for Ring to finish the recording, then finds the event's start and end in Ring's history.
3. It downloads 4 stills from across the opening. Amazon Rekognition finds any faces and each one is blurred before the still is stored in S3, so no unblurred face reaches S3, the app or Nova. If face detection fails, that still is dropped rather than stored. The stills are deleted after 7 days.
4. It checks the brightness of the area where the fridge light shows. Motion without the door opening stops here, so no Nova call is made.
5. Amazon Nova 2 Lite compares the stills and lists items added and removed. Changes with confidence 0.7 or more update the inventory; the rest wait for confirmation.

Nova 2 Lite runs through the `us.` cross-region inference profile, so a still may be processed in us-east-1, us-east-2 or us-west-2. To use Nova Lite v1 in us-east-1 only, deploy with `-c novaModelId=amazon.nova-lite-v1:0 -c novaPriceIn=0.00006 -c novaPriceOut=0.00024`.

### 6. Tune the door check

The door box (fractions `x,y,width,height` of the image) and the brightness threshold are guesses until the camera is mounted. Open and close the fridge a few times, wave at the camera with the door shut, then read the brightest values the pipeline saw:

```bash
set -a; source .env; set +a; aws logs tail /fridgesense/pipeline --since 1h --filter-pattern '"motion_not_door"'
```

Each line shows `brightest` and `threshold`. Pick a threshold between the closed-door values and the open-door ones, adjust the box if needed, and deploy:

```bash
set -a; source .env; set +a; cd infra && npx cdk deploy -c doorBox=0.25,0.1,0.5,0.8 -c doorThreshold=0.5
```

### Nova cost per opening

Every Nova call logs its token use and cost:

```bash
set -a; source .env; set +a; aws logs tail /fridgesense/pipeline --since 24h --filter-pattern '"nova_cost"'
```

Each door event also stores its total as `nova_usd`. Expect about $0.0014 per opening with Nova 2 Lite.

### Face detection cost

Every face-detection call (one per still, so four per motion event) logs its cost:

```bash
set -a; source .env; set +a; aws logs tail /fridgesense/pipeline --since 24h --filter-pattern '"face_detect_cost"'
```

Expect $0.001 per still. Failed calls log `face_detect_failed` instead, with the still number and error. To change the price used in the log, deploy with `-c faceDetectPrice=0.0008`.

### Remove

```bash
set -a; source .env; set +a; cd infra && npx cdk destroy
```

The DynamoDB table and the `fridgesense/ring-app` secret are kept; delete them in the console if you no longer need them.

## License

MIT — see [LICENSE](LICENSE).
