# Proposal

## Why

The Alexa+ track (the biggest prize pool) requires "a self-hosted MCP server, implementing MCP spec version 2025-11-25 … over Streamable HTTP". The demo line is "Alexa, do I have milk?". The fridge data already exists. This change exposes it as a small, read-only MCP server whose answers read well aloud.

Tracks: **Alexa+** (the MCP server) and **AWS Builder** (serverless MCP on Lambda behind the existing HTTP API).

## What Changes

- **A stateless Streamable HTTP MCP server** at `https://<api>/mcp/<key>`, built with the official MCP Python SDK (2.x) and served by a new Lambda through the existing HTTP API.
  - The `<key>` path segment is a long random value stored in the app secret.
  - Without the right key, or with no key configured, the endpoint answers 404, so the URL works with any MCP client (Alexa+, MCP Inspector, Claude Desktop) without OAuth.
- **Four read-only tools**, each with `readOnlyHint` and a structured output schema:
  - `find_item(name)`: "Do I have milk?"
  - `get_inventory(category?)`: "What's in my fridge?"
  - `fridge_activity(period)`: "How often did we open the fridge today?"
  - `last_opened()`: "When was the fridge last opened, and what changed?"
- **Voice-friendly results:**
  - Counts, names, minutes ago, and local times in the household's time zone.
  - Always a result rather than an empty answer.
  - Matching that forgives plurals, case and partial names ("eggs" → "eggs", "milk" → "whole milk").
- **A warm-up schedule** keeps the MCP Lambda warm, because Alexa+ expects tool round trips under 500 ms.
- **The README** gains connection steps for MCP Inspector, Claude Desktop and the Alexa+ MCP Toolkit (`alexa-ai` CLI), and the command that sets the key.

## Capabilities

### New Capabilities

- `fridge-mcp`: the MCP endpoint and its four tools for voice assistants and other MCP clients.

### Modified Capabilities

None.

## Out of scope

- **Write tools** (confirm, reject, set quantity). Voice stays read-only for the demo.
- **OAuth 2.1 and per-user account linking.** There is one household, and access is protected by the URL key.
- **The simulated Alexa+ experience.** If Amazon's Alexa+ MCP Toolkit turns out to be gated for hackathon entrants (its setup mentions an Alexa Solutions Architect and an Amazon-provided role), a voice page in the PWA becomes a separate follow-up change. The rules allow a simulated experience.
- **Recipes and "what can I cook"** (the Strands agent stays cut), plus low-stock and oldest-item tools.
- **Publishing an Alexa+ add-on.** Icons, privacy and terms URLs and certification come only if the toolkit works for this account.

## Impact

- **New code:** `backend/src/fridgesense/mcp_server.py` and `handlers/mcp.py`. New dependencies: `mcp>=2.3,<3` and `mangum`. `mcp` pulls in `httpx2`, which sits alongside the existing `httpx`.
- **AWS:** one Lambda (arm64), one route `ANY /mcp/{key}`, and one EventBridge rule every 5 minutes. Cost is cents per month; the warm-up adds about 8,600 short invocations a month, which the free tier covers.
- **Config:**
  - `mcp_key` in `fridgesense/ring-app`
  - a `timeZone` CDK context value (default `America/Toronto`, to confirm) so "today" means the household's day
- **Lambda package size:** the shared Lambda asset grows by the MCP SDK (a few MB).
