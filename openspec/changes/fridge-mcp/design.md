# Design

## Context

The single table holds what the tools need, under `ACCOUNT#<account_id>`:
- `ITEM#<key>` (name, category, quantity, last_changed_at)
- `DOOR#<opened_at>#<device>` (duration_s, status, changes with applied/rejected flags, pending_count)
- `PENDING#…`

`FridgeTable`, `TokenStore` and `load_app_config` already exist, and the HTTP API serves `/ring/*` and `/api/*`. See proposal.md for scope.

SDK facts were checked on Oct 14 against `mcp` 2.3.0 with a working scratch prototype:
- **API:** `FastMCP` is now `mcp.server.mcpserver.MCPServer`. `streamable_http_app(streamable_http_path=…, stateless_http=True, json_response=True, transport_security=…)` returns a Starlette app.
- **Protocol versions:** it negotiates 2024-11-05 through 2025-11-25.
- **Structured output:** it generates `outputSchema` and `structuredContent` from Pydantic return types.
- **Host check:** DNS-rebinding protection is on by default and answers 421 for an execute-api `Host`.
- **One run per app:** `StreamableHTTPSessionManager.run()` works once per app instance, and Mangum runs lifespan on every invocation. A reused app fails on the second warm call.

## Goals / Non-Goals

**Goals:**
- One MCP URL that works unchanged in MCP Inspector, Claude Desktop and the Alexa+ MCP Toolkit.
- Warm tool round trips well under Alexa's 500 ms budget: one or two DynamoDB queries and no Ring calls.

**Non-Goals:**
- MCP prompts, resources or MCP Apps.
- Writes over MCP.
- Sessions (the server is stateless).

## Decisions

### Server: MCP Python SDK 2.x, stateless JSON mode
- `mcp_server.py` defines `MCPServer("fridgesense", instructions=…)` and the four tools.
- Each tool is a thin async function over a pure "answer" function that takes a table, an account ID, a clock and a time zone, so the logic is tested without MCP.
- Return types are Pydantic models, so `outputSchema` and `structuredContent` come for free.
- Annotations are `ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)`.
- *Alternative:* pin `mcp<2` and keep `FastMCP`. That's older code, and the 2.x docs and migration guide are where fixes land.

### Lambda adapter: Mangum with a fresh app per invocation
- The handler checks the key, then calls `Mangum(build_app(), lifespan="on")(event, context)`.
- Building the Starlette app costs well under a millisecond. Module-level objects (the `MCPServer`, boto3 clients) stay warm.
- DNS-rebinding protection is off. API Gateway is the only way in, and the URL key is the access control.
- *Alternative:* AWS Lambda Web Adapter with uvicorn. That needs a layer and its own startup command, and it's untested here.

### Access: a key in the path, not OAuth
- Route `ANY /mcp/{key}`. The handler compares `key` with `mcp_key` from `fridgesense/ring-app` in constant time. A mismatch or a missing key is 404 before Mangum runs.
- The Starlette app is mounted at `/mcp/<key>` for the request, so the SDK sees its expected path.
- **Why:**
  - Alexa+ Tier 1 auth needs an OAuth client-credentials token endpoint, and Tier 2 needs full OAuth 2.1 with PKCE.
  - The data is one household's item counts and door times, and the tools are read-only.
  - A 32-byte random path key matches the risk and works with every client.
- **Key rotation:** set a new `mcp_key` and re-register the URL.

### Matching item names
- `normalize(q)`: lower case, collapse spaces, then strip a trailing `es` (for words ending in `s`, `x`, `ch` or `sh`) or a trailing `s` (not `ss`) from the last word.
- An item matches when its normalized name equals the normalized query, or contains it as a whole word.
- This covers "eggs" against "egg" or "eggs", and "milk" against "whole milk", without fuzzy-match libraries.

### Time
- `TIME_ZONE` env (an IANA name) comes from CDK context `timeZone`, default `America/Toronto`, to be confirmed with Jayson. `zoneinfo` handles it.
- "today" means `[local midnight, now]`; "week" means local midnight 6 days ago to now. Both are queried as `sk BETWEEN DOOR#<start UTC ISO> AND DOOR#~`.
- `minutes_ago` is a floored integer from an injectable clock.

### Warm-up
- An EventBridge rule every 5 minutes invokes the MCP Lambda with `{"warmup": true}`. The handler returns at once, without calling AWS.
- Memory is 512 MB. The MCP SDK imports faster with more CPU, and a warm call costs the same.
- *Alternative:* provisioned concurrency. It guarantees warmth but costs about $3–6 a month, which isn't worth it for a demo.

### Infrastructure
- **Lambda:** `fridgesense.handlers.mcp.handler`, arm64, 512 MB, 10 s, log group `/fridgesense/mcp`, env = shared vars + `TIME_ZONE`.
- **Grants:** table read only, app secret read, token secret read.
- **Route:** `ANY /mcp/{key}` on the existing HTTP API.
- **Output:** `McpUrlTemplate` = `<api>/mcp/<key>`, with the key left for the README command to fill.

## Test strategy

| Level | What | How |
| --- | --- | --- |
| Unit (pytest) | `normalize` and matching; each answer function (find, inventory, activity, last opened) against moto DynamoDB with seeded items and door events and a fixed clock and time zone | Pure functions + `aws` fixture |
| MCP protocol (pytest) | `tools/list` (names, annotations, outputSchema) and `tools/call` for each tool, including validation errors and "No camera is linked" | In-memory `mcp.Client(server, mode="legacy")`: real initialize handshake, no network |
| HTTP/Lambda (pytest) | Initialize with 2025-11-25 and 2025-03-26 through `handlers.mcp.handler` using API Gateway v2 events with an execute-api `Host`; two warm calls in a row; wrong key, no key and warm-up events | Synthetic events; moto for the secret |
| Infra (Vitest) | Lambda settings, `ANY /mcp/{key}` route, the 5-minute warm-up rule, read-only table grant (no Put/Update/Delete), no Bedrock, S3 or Step Functions | `Template.fromStack` |

Nothing calls Ring, AWS or an Alexa endpoint. The Alexa+ connection is checked by hand (see Risks).

## Risks / Trade-offs

- [The Alexa+ MCP Toolkit is gated (its setup mentions an Alexa Solutions Architect and an Amazon-provided IAM role)] → Try `alexa-ai configure` early (Jayson, Oct 15–16). If it's blocked, the demo uses MCP Inspector plus a simulated Alexa+ voice page in a follow-up change; the rules explicitly allow a simulated experience. I won't create IAM users or roles for it.
- [Cold start over 500 ms] → The warm-up rule keeps one instance warm. Alexa's first call after a long idle may still be slow, which is acceptable for a demo; record the video after a warm-up.
- [A URL key is weaker than OAuth] → The data is read-only and low-sensitivity, and the key is rotatable. The README says to keep the URL private and remove the key after judging.
- [`mcp` 2.x moves fast] → Pin `mcp>=2.3,<3` in the lockfile; the protocol tests catch breaking changes.
- [The time zone default is wrong] → It's a deploy-time context value; confirm it before deploying.

## Open Questions

- The household time zone (default `America/Toronto`). Changing it is config only.
