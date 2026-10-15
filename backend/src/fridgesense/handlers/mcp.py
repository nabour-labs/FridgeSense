"""MCP Lambda: Streamable HTTP at /mcp/<key>, stateless JSON responses.

Mangum runs the ASGI lifespan on every invocation and the SDK's session manager can only run
once per app, so each invocation gets a fresh Starlette app around the shared MCPServer.
"""

import hmac
import logging

from mangum import Mangum
from mcp.server.transport_security import TransportSecuritySettings

from fridgesense.logs import log_event
from fridgesense.mcp_server import build_server, default_context
from fridgesense.store import load_app_config
from fridgesense.web import json_response

server = build_server(default_context)

# API Gateway is the only way in and the path key is the access control; the SDK's
# DNS-rebinding check would reject the execute-api Host header.
_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)


def build_app(path: str):
    return server.streamable_http_app(
        streamable_http_path=path,
        stateless_http=True,
        json_response=True,
        transport_security=_SECURITY,
    )


def handler(event, context):
    if event.get("warmup"):
        return {"warm": True}
    logging.getLogger().setLevel(logging.INFO)
    key = (event.get("pathParameters") or {}).get("key", "")
    expected = load_app_config().mcp_key
    if not expected or not hmac.compare_digest(key.encode(), expected.encode()):
        log_event("mcp_rejected", logging.WARNING)
        return json_response(404, {"error": "not found"})
    return Mangum(build_app(f"/mcp/{key}"), lifespan="on")(event, context)
