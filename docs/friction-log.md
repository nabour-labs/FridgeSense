# Friction log

This file records friction we hit with the services the hackathon covers: the Ring Partner API, Alexa+, AWS (Bedrock Nova, Rekognition, CDK, Step Functions, Lambda, S3, DynamoDB and the rest), MCP and Strands, and Fire TV. Add an entry as soon as the friction happens, while the details are fresh. The submission's friction log and product feedback are built from these entries.

**Severity:**
- **High:** blocks the task, with no workaround.
- **Medium:** costs real time or changes the design.
- **Low:** annoying but quick to work around.

Each entry uses this template. Put the newest entry first.

```markdown
### YYYY-MM-DD · <service> · <one-line title>

- **Task:** what we were trying to do
- **Steps:** what we did, in order (commands, endpoints, console pages)
- **Expected:** what we thought would happen
- **Actual:** what happened (exact error text when there is one)
- **Severity:** High / Medium / Low
- **Workaround:** how we got past it (or "none yet")
- **Suggestion:** what the service could change
```

## Entries

### 2026-10-14 · Alexa+ · MCP Toolkit setup looks gated for hackathon entrants

- **Task:** connect the FridgeSense MCP server to Alexa+ for the Alexa+ track.
- **Steps:** read the Alexa+ MCP Toolkit overview, quickstart and "Set up your development environment" pages under `developer.amazon.com/docs/alexaplus/add-ons/`.
- **Expected:** a self-serve path: install the `alexa-ai` CLI, sign in, register an MCP server URL, test in the simulator.
- **Actual:** setup refers to "the AWS account that you provided to the Alexa Solutions Architect", an IAM user that assumes an Amazon-provided role, and a private CodeArtifact registry. It isn't clear whether hackathon entrants get that access. The hackathon rules don't mention it either.
- **Severity:** Medium
- **Workaround:** none yet. We build to the rules (MCP 2025-11-25 over Streamable HTTP), test with MCP Inspector, and keep a simulated Alexa+ experience (allowed by the rules) as the fallback.
- **Suggestion:** say on the hackathon resources page whether entrants can use the Alexa+ MCP Toolkit, and how to request access.

### 2026-10-14 · MCP Python SDK · v2 breaks v1 code and needs care on Lambda

- **Task:** serve a stateless Streamable HTTP MCP server from AWS Lambda.
- **Steps:** installed `mcp` 2.3.0, followed v1-era examples (`FastMCP`), wrapped the Starlette app with Mangum, called it through an API Gateway event.
- **Expected:** v1 examples work; one ASGI app can serve many Lambda invocations.
- **Actual:** `mcp.server.fastmcp` now raises an error pointing to the migration guide (renamed to `MCPServer`). Reusing one Mangum-wrapped app fails on the second warm call with `LifespanFailure: ... run() can only be called once per instance`. The default DNS-rebinding protection answers `421 Invalid Host header` for the execute-api host.
- **Severity:** Medium
- **Workaround:** build a fresh app per invocation (`Mangum(build_app(), lifespan="on")`) and pass `TransportSecuritySettings(enable_dns_rebinding_protection=False)`.
- **Suggestion:** an official serverless/Lambda example for stateless Streamable HTTP, and a session manager that can run more than once.

### 2026-10-14 · Amazon Bedrock · Nova 2 Lite has no in-region on-demand in us-east-1

- **Task:** call Nova 2 Lite with the Converse API from a us-east-1 Lambda.
- **Steps:** read the Nova 2 Lite model card.
- **Expected:** `amazon.nova-2-lite-v1:0` works on-demand in us-east-1, as the model card's own code sample shows.
- **Actual:** the availability table marks in-region as unsupported in us-east-1; only the `us.` (geo) and `global.` inference profiles work. The `us.` profile can route to us-east-2 and us-west-2 and costs about 10% more than `global.`. IAM then needs the profile ARN plus the foundation-model ARN in each destination region.
- **Severity:** Low
- **Workaround:** use `us.amazon.nova-2-lite-v1:0` and grant `bedrock:InvokeModel` on the profile and the three regional model ARNs.
- **Suggestion:** use the profile ID in the model card sample and say which regions a geo profile can route to on the same page.

### 2026-10-14 · Amazon Bedrock · Structured outputs not available for Nova

- **Task:** get a guaranteed JSON answer (items added and removed) from Nova.
- **Steps:** looked at Converse `outputConfig` structured outputs.
- **Expected:** JSON-schema structured output, as on other Bedrock models.
- **Actual:** both Nova 2 Lite and Nova Lite list structured outputs (and `strict`) as not supported.
- **Severity:** Low
- **Workaround:** a forced tool (`toolChoice: {"tool": {"name": "record_fridge_changes"}}`) at temperature 0, then Pydantic validation and one retry.
- **Suggestion:** support `outputConfig` JSON schemas on Nova models.

### 2026-10-14 · Ring Partner API · Token Exchange request format undocumented

- **Task:** implement the Token Exchange URL for one-way account linking.
- **Steps:** read the authentication section of the API documentation and the `AmazonAppDev/ring-api-helloworld` sample.
- **Expected:** the exact request Ring sends to the Token Exchange URL (content type and field names) and the response it expects.
- **Actual:** the docs only show sequence-diagram labels ("POST authorization code to Partner Token Exchange URL", "exchange within 60 seconds", "returns 200"). The sample doesn't implement account linking. The sample's webhook check is a plain bearer token, not the documented `X-Signature` HMAC, and its schema still lists `person_detected`.
- **Severity:** Medium
- **Workaround:** accept `code` from JSON, a form or the query string, and log only the field names so the first real link shows the format.
- **Suggestion:** document the Token Exchange request and response with an example, and update the sample to verify `X-Signature` over the raw body.

### 2026-10-14 · AWS Lambda + uv · Pillow 12 has no manylinux2014 wheels

- **Task:** bundle Pillow for a Python 3.13 arm64 Lambda with `uv pip install --python-platform aarch64-manylinux2014 --only-binary :all:` (no Docker).
- **Steps:** `cdk synth` with local uv bundling.
- **Expected:** arm64 wheels for every dependency.
- **Actual:** `Because pillow==12.3.0 has no usable wheels ... your requirements are unsatisfiable.` Pillow 12 ships only `manylinux_2_28` wheels.
- **Severity:** Low
- **Workaround:** target `aarch64-manylinux_2_28`; the python3.13 runtime runs on Amazon Linux 2023 (glibc 2.34).
- **Suggestion:** state the runtime's glibc and the matching manylinux tag on the Lambda Python runtime page.

### 2026-10-14 · AWS CDK · `TableV2` creates a global table

- **Task:** a single-region on-demand DynamoDB table in CDK.
- **Steps:** used `TableV2` (the newer construct) and asserted `AWS::DynamoDB::Table` in tests.
- **Expected:** a plain table.
- **Actual:** `TableV2` always synthesizes `AWS::DynamoDB::GlobalTable`, even with one region.
- **Severity:** Low
- **Workaround:** use the classic `Table` construct.
- **Suggestion:** mention in the `TableV2` docs that it is a global table resource even for one region.
