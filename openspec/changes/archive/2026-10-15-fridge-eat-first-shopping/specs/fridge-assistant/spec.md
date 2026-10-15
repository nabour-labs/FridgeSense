## MODIFIED Requirements

### Requirement: Tools come from the MCP server
For each question, the assistant SHALL connect to the FridgeSense MCP server over Streamable HTTP at `https://<api host>/mcp/<mcp_key>`, list its tools, and offer exactly those tools to the model, each with the name, description and input schema the server gave.

#### Scenario: Four tools offered
- **WHEN** the assistant answers "Do I have milk?" against the FridgeSense MCP server
- **THEN** the original four tools `find_item`, `get_inventory`, `fridge_activity` and `last_opened` are still among the tools offered

#### Scenario: Six tools offered
- **WHEN** the assistant answers "Do I have milk?" against the FridgeSense MCP server
- **THEN** the first model request's tool config lists `find_item`, `get_inventory`, `fridge_activity`, `last_opened`, `oldest_items` and `low_stock`, each with its MCP description and its input schema as `inputSchema.json`

#### Scenario: MCP URL
- **WHEN** the API host is `abc123.execute-api.us-east-1.amazonaws.com` and `mcp_key` is `k1`
- **THEN** the assistant connects to `https://abc123.execute-api.us-east-1.amazonaws.com/mcp/k1`
