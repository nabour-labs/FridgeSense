"""fridge-mcp: the MCP server over an in-memory client (real handshake, no network)."""

from zoneinfo import ZoneInfo

import pytest
from mcp import Client

from fridgesense.mcp_server import FridgeContext, build_server
from fridgesense.table import FridgeTable
from tests.mcp_helpers import ACCOUNT, NOW, change, put_door, put_item

pytestmark = pytest.mark.anyio
TOOLS = [
    "find_item",
    "get_inventory",
    "fridge_activity",
    "last_opened",
    "oldest_items",
    "low_stock",
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def server(aws):
    def context():
        return FridgeContext(FridgeTable(), ACCOUNT, NOW, ZoneInfo("America/Toronto"))

    return build_server(context)


# Tool list
async def test_tool_list(server):
    async with Client(server, mode="legacy") as client:
        tools = (await client.list_tools()).tools
    assert sorted(t.name for t in tools) == sorted(TOOLS)
    for tool in tools:
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.destructive_hint is False, tool.name
        assert tool.annotations.idempotent_hint is True, tool.name
        assert tool.output_schema, tool.name
        assert len(tool.description or "") > 20, tool.name


async def test_server_info(server):
    async with Client(server, mode="legacy") as client:
        assert client.server_info.name == "fridgesense"


async def test_find_item_call(server):
    put_item("milk", 1, minutes_ago=12)
    async with Client(server, mode="legacy") as client:
        result = await client.call_tool("find_item", {"name": "milk"})
    assert result.is_error is False
    assert result.structured_content["in_fridge"] is True
    assert result.structured_content["matches"][0]["minutes_ago"] == 12


async def test_get_inventory_call(server):
    put_item("eggs", 6)
    async with Client(server, mode="legacy") as client:
        all_items = await client.call_tool("get_inventory", {})
        dairy = await client.call_tool("get_inventory", {"category": "dairy"})
    assert all_items.structured_content["total_items"] == 1
    assert dairy.structured_content["items"][0]["name"] == "eggs"


async def test_fridge_activity_call(server):
    put_door(NOW.replace(hour=12), 30)
    async with Client(server, mode="legacy") as client:
        result = await client.call_tool("fridge_activity", {"period": "today"})
    assert result.structured_content["opens"] == 1


async def test_last_opened_call(server):
    put_door(NOW.replace(hour=23, minute=57), 18, [change("milk")])
    async with Client(server, mode="legacy") as client:
        result = await client.call_tool("last_opened", {})
    assert result.structured_content["added"] == [{"name": "milk", "count": 1}]


async def test_oldest_items_call(server):
    put_item("milk", 1, stocked_at="2026-10-11T00:00:00.000Z")
    put_item("ketchup", 1, "condiment", stocked_at="2026-09-01T00:00:00.000Z")
    async with Client(server, mode="legacy") as client:
        result = await client.call_tool("oldest_items", {})
        condiments = await client.call_tool("oldest_items", {"category": "condiment", "limit": 1})
    assert result.is_error is False
    assert result.structured_content["items"][0]["name"] == "milk"
    assert result.structured_content["items"][0]["days_in_fridge"] == 5
    assert condiments.structured_content["items"][0]["name"] == "ketchup"


async def test_low_stock_call(server):
    put_item("milk", 0, minutes_ago=90)
    put_item("eggs", 2, peak_quantity=12)
    async with Client(server, mode="legacy") as client:
        result = await client.call_tool("low_stock", {})
    assert result.is_error is False
    assert result.structured_content["ran_out"][0]["name"] == "milk"
    assert result.structured_content["running_low"][0]["usual_count"] == 12


# Limit out of range
@pytest.mark.parametrize("limit", [0, 21])
async def test_limit_out_of_range(server, monkeypatch, limit):
    calls = []
    monkeypatch.setattr(FridgeTable, "query", lambda *a, **k: calls.append(a) or [])
    async with Client(server, mode="legacy") as client:
        result = await client.call_tool("oldest_items", {"limit": limit})
    assert result.is_error is True
    text = " ".join(getattr(c, "text", "") for c in result.content)
    assert "limit" in text and ("1" in text or "20" in text)
    assert calls == []


# Unknown period
async def test_unknown_period(server, monkeypatch):
    calls = []
    monkeypatch.setattr(FridgeTable, "query_range", lambda *a, **k: calls.append(a) or [])
    async with Client(server, mode="legacy") as client:
        result = await client.call_tool("fridge_activity", {"period": "year"})
    assert result.is_error is True
    text = " ".join(getattr(c, "text", "") for c in result.content)
    assert "today" in text and "week" in text
    assert calls == []


# Not linked
@pytest.mark.parametrize(
    ("tool", "args"), [("find_item", {"name": "milk"}), ("oldest_items", {}), ("low_stock", {})]
)
async def test_not_linked(aws, tool, args):
    from fridgesense.mcp_server import default_context

    async with Client(build_server(default_context), mode="legacy") as client:
        result = await client.call_tool(tool, args)
    assert result.is_error is True
    assert "No camera is linked" in " ".join(getattr(c, "text", "") for c in result.content)
