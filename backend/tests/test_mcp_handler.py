"""fridge-mcp: the Lambda endpoint (URL key, Streamable HTTP through API Gateway)."""

import json

import pytest

from fridgesense.handlers import mcp as mcp_handler
from fridgesense.store import load_app_config
from tests.api_helpers import configure, link_account
from tests.mcp_helpers import put_item

KEY = "k" * 64
HOST = "abc123.execute-api.us-east-1.amazonaws.com"


def event(key: str, body: dict, protocol: str | None = None, method: str = "POST") -> dict:
    headers = {
        "host": HOST,
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
    }
    if protocol:
        headers["mcp-protocol-version"] = protocol
    path = f"/mcp/{key}"
    return {
        "version": "2.0",
        "routeKey": "ANY /mcp/{key}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": headers,
        "pathParameters": {"key": key},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "abc123",
            "domainName": HOST,
            "domainPrefix": "abc123",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.7",
                "userAgent": "test",
            },
            "requestId": "r1",
            "routeKey": "ANY /mcp/{key}",
            "stage": "$default",
            "time": "16/Oct/2026:00:00:00 +0000",
            "timeEpoch": 1791936000000,
        },
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def initialize(version: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": version,
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }


def call(evt):
    resp = mcp_handler.handler(evt, None)
    body = resp.get("body") or ""
    return resp["statusCode"], (json.loads(body) if body.startswith("{") else body)


@pytest.fixture
def keyed(aws):
    configure(mcp_key=KEY)
    load_app_config(refresh=True)
    link_account()


# Initialize with 2025-11-25
def test_initialize_2025_11_25(keyed):
    status, body = call(event(KEY, initialize("2025-11-25")))
    assert status == 200
    assert body["result"]["protocolVersion"] == "2025-11-25"
    assert body["result"]["serverInfo"]["name"] == "fridgesense"
    assert "tools" in body["result"]["capabilities"]


# Older client version
def test_older_client_version(keyed):
    status, body = call(event(KEY, initialize("2025-03-26")))
    assert status == 200 and body["result"]["protocolVersion"] == "2025-03-26"


# Wrong key
def test_wrong_key(keyed, monkeypatch):
    monkeypatch.setattr(mcp_handler, "Mangum", lambda *a, **k: pytest.fail("MCP server reached"))
    assert call(event("not-the-key", initialize("2025-11-25")))[0] == 404


# No key configured
@pytest.mark.parametrize("key", ["", "anything"])
def test_no_key_configured(aws, key):
    load_app_config(refresh=True)
    assert call(event(key, initialize("2025-11-25")))[0] == 404


# Request through API Gateway: execute-api Host, two warm invocations in a row
def test_request_through_api_gateway(keyed):
    first = call(event(KEY, initialize("2025-11-25")))
    second = call(event(KEY, initialize("2025-11-25")))
    assert first[0] == 200 and second[0] == 200


def test_tools_call_over_http(keyed):
    put_item("milk", 1)
    call(event(KEY, initialize("2025-11-25")))
    status, body = call(
        event(
            KEY,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "find_item", "arguments": {"name": "milk"}},
            },
            protocol="2025-11-25",
        )
    )
    assert status == 200
    assert body["result"]["structuredContent"]["in_fridge"] is True
    assert body["result"]["isError"] is False


def test_warmup_returns_without_aws(monkeypatch):
    monkeypatch.setattr(
        mcp_handler, "load_app_config", lambda *a, **k: pytest.fail("AWS called on warm-up")
    )
    assert mcp_handler.handler({"warmup": True}, None) == {"warm": True}
