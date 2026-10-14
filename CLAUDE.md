# FridgeSense

A Ring Indoor Cam 2K watches the fridge. Each door opening triggers a Ring webhook; the clip and stills go to S3, Amazon Bedrock Nova lists what was added or removed, and the app keeps a running inventory plus open/close stats. Front ends: a PWA and an MCP server for Alexa+ ("do I have milk?").

- Full plan, Ring API notes and hackathon rules: [docs/hackathon-plan.md](docs/hackathon-plan.md)
- Deadline: **Fri Oct 23 2026, 12:00 pm PT**. Prefer the smallest change that works; Fire TV only if everything else is done by Oct 20.

## Workflow: OpenSpec + TDD

All feature work goes through OpenSpec (`openspec/`), and all code is written test-first.

1. `/opsx:propose <idea>` — creates `openspec/changes/<name>/` with proposal, spec deltas, design and tasks
2. Review the change, then `/opsx:apply` — work the tasks in order
3. `/opsx:archive` — once tests are green, merges spec deltas into `openspec/specs/`

Other commands: `/opsx:explore` (think before proposing), `/opsx:update`, `/opsx:sync`. CLI: `openspec list`, `openspec show <change>`, `openspec validate <change>`.

TDD rules (also enforced in `openspec/config.yaml`):

- **Red → green → refactor.** Write the failing test first and run it to see it fail for the right reason. Then write the least code that makes it pass. Then refactor with tests green.
- Every spec scenario (WHEN/THEN) maps to at least one test. Name tests after the scenario.
- Never skip, weaken or delete a test to get green. If the spec is wrong, change the spec first.
- Tests never hit live Ring, AWS or Bedrock: use recorded webhooks and canned responses under `tests/fixtures/`, moto or botocore Stubber for AWS, and stubbed Bedrock Converse responses.
- Report the test command and its result when finishing a task.

## Stack

- **Python 3.13** (uv, pytest, ruff, Pydantic): Ring client, Lambdas, Step Functions tasks, Nova analysis, Strands agent, MCP server (official Python SDK, Streamable HTTP, spec 2025-11-25)
- **TypeScript**: PWA (Vite + React + vite-plugin-pwa + Tailwind + Recharts, Vitest) and AWS CDK infrastructure
- AWS us-east-1: API Gateway HTTP API, Lambda, Step Functions, DynamoDB (single table), S3, Secrets Manager, Cognito, Bedrock Nova

## Accounts and credentials

You have no AWS or GitHub accounts of your own. Every Bash command runs as Jayson on his Mac and uses his credentials, so anything you do on GitHub or AWS is done as him.

**AWS (CLI and CDK)**

- Always use the profile named by `AWS_PROFILE` in `.env`. Never use the default profile and never hard-code a profile name.
- Load it into the shell before any `aws` or `cdk` command, without printing `.env`:

  ```bash
  set -a; source .env; set +a; aws sts get-caller-identity
  ```

  Shell state does not persist between Bash calls, so load `.env` in the same command each time.
- If `AWS_PROFILE` is missing or empty, stop and ask. Do not fall back to another profile.
- Region: us-east-1.
- The profile's IAM permissions are the limit of what you can do. Never create or change IAM users, roles or access keys to get around a permission error; report the error instead.
- Reads (`describe`, `list`, `get`, `cdk diff`, `cdk synth`, CloudFormation reads) are fine. Ask before anything that creates, changes, deletes or costs money: `cdk deploy`, `cdk destroy`, deleting S3 objects or DynamoDB items, and Bedrock calls outside tests.

**GitHub**

- `gh` is logged in as `jnabor`. Its token is in the macOS keychain or `~/.config/gh/hosts.yml`; never read or print it.
- `origin` uses an SSH URL, but `git push` goes over HTTPS through the `gh` credential helper. If a push fails on auth, check `gh auth status` and the helper (`git config --get-all credential.https://github.com.helper`) rather than SSH keys.
- PRs, comments, issues and pushes show up as `jnabor`. Ask before pushing, opening a PR or posting anything.

**Branches and PRs**

- `main` is protected: never commit or push to it directly. Work on a feature branch (e.g. `feat/<openspec-change-name>`) and merge through a PR.
- Every PR to `main` must pass the `unit-tests` check ([.github/workflows/unit-tests.yml](.github/workflows/unit-tests.yml)). It runs pytest for each Python project and `npm test` for each Node package whenever the PR changes code; PRs that only touch docs, `openspec/`, `.claude/` or Markdown pass without running tests.
- Run the same tests locally before opening a PR. New Python projects need a `pyproject.toml` with pytest as a dev dependency; new Node packages need a `test` script that runs once and exits (e.g. `vitest run`).
- Branch protection is applied by [scripts/protect-main.sh](scripts/protect-main.sh). Only `jnabor` can merge into `main`. Because you run as `jnabor`, never merge a PR unless Jayson explicitly asks.

## Hard rules

- Credentials and secrets live in config or Secrets Manager, never in code or commits. Ring Client Secret and webhook signing key are shown only once — keep them out of the repo.
- Key all stored data by Ring `account_id` and device ID.
- Webhook handler: verify `X-Signature` (HMAC-SHA256 of the raw body, `sha256=` hex) first, skip duplicates by `meta.request_id`, reply 200 within 5 s, and do the work asynchronously. Avoid 4xx responses to Ring (10+ in a row can disable the webhook).
- Raw clips auto-delete after ~7 days; support "delete my data".
- The product name never includes "Ring", "Amazon" or "Alexa".
- AWS costs are paid out of pocket: only analyze real door openings and log Nova cost per clip.
