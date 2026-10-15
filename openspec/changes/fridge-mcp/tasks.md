# Tasks

## 1. Setup

- [x] 1.1 Add `mcp>=2.3,<3` and `mangum` to backend dependencies and `mcp_key` (default empty) to `AppConfig`; verify `uv run pytest` still passes and `uv export --no-dev` lists `mcp`, `httpx2` and `mangum`

## 2. Answer functions

- [ ] 2.1 Write failing unit tests for `normalize` and matching ("eggs" vs "egg", "milk" vs "whole milk", "glass" keeps its "ss", case and spaces); then implement them and verify the tests pass
- [ ] 2.2 Write failing moto tests for "Do I have milk?", "Plural and partial names", "Several matches", "Run out" and "Never seen"; verify they fail
- [ ] 2.3 Implement the find answer (with `minutes_ago` from an injected clock) to make the tests pass
- [ ] 2.4 Write failing moto tests for "Whole fridge" and "One category"; then implement the inventory answer and verify they pass
- [ ] 2.5 Write failing moto tests for "Opens today" (America/Toronto, fixed clock) and "No opens"; then implement the activity answer with a local-midnight window and verify they pass
- [ ] 2.6 Write failing moto tests for "Milk just went in" and "Never opened"; then implement the last-opened answer and verify they pass

## 3. MCP server

- [ ] 3.1 Write failing in-memory `mcp.Client` tests for "Tool list" (names, annotations, outputSchema) and `tools/call` of each tool returning `structuredContent`; verify they fail
- [ ] 3.2 Implement `mcp_server.py` (an `MCPServer` with the four tools wired to the answer functions) to make the tests pass
- [ ] 3.3 Write failing tests for "Unknown period" and "Not linked"; then implement the validation (`Literal["today", "week"]`) and the no-account error, and verify they pass

## 4. Lambda endpoint

- [ ] 4.1 Write failing handler tests (API Gateway v2 events, moto secret) for "Initialize with 2025-11-25", "Older client version", "Wrong key", "No key configured", "Request through API Gateway" (execute-api `Host`, two warm calls) and a warm-up event returning without AWS calls; verify they fail
- [ ] 4.2 Implement `handlers/mcp.py` (warm-up short-circuit, constant-time key check, Mangum with a fresh app per call, DNS-rebinding protection off) to make the tests pass

## 5. Infrastructure

- [ ] 5.1 Write failing Vitest assertions for the MCP Lambda (handler, arm64, 512 MB, 10 s, `TIME_ZONE` env, log group `/fridgesense/mcp`), the `ANY /mcp/{key}` route, the `rate(5 minutes)` warm-up rule with `{"warmup": true}`, read-only table access (no Put/Update/Delete/BatchWrite), secrets read-only, and no Bedrock, S3 or Step Functions permissions; verify they fail
- [ ] 5.2 Implement the MCP construct and the `timeZone` context to make the tests pass; verify `cdk synth` with real bundling includes `mcp` and `mangum` in the Lambda asset

## 6. Docs and final check

- [ ] 6.1 Update the README: setting `mcp_key` (generated with `openssl rand -hex 32`), building the URL from the `McpUrlTemplate` output, connecting MCP Inspector and Claude Desktop, the Alexa+ MCP Toolkit steps (`alexa-ai configure`, `alexa-ai new mcp --mcp-server-url …`, `alexa-ai deploy`, test in the developer console simulator), example questions, and keeping the URL private; verify the commands match the code
- [ ] 6.2 Run `cd backend && uv run pytest && uv run ruff check && uv run ruff format --check` and `cd infra && npm test && npx tsc --noEmit`; all green
