"""fridge-assistant: answer cleanup, the MCP URL and Converse tool specs."""

from zoneinfo import ZoneInfo

import pytest
from mcp import Client

from fridgesense import assistant
from fridgesense.mcp_server import FridgeContext, build_server
from fridgesense.table import FridgeTable
from tests.mcp_helpers import ACCOUNT, NOW

TOOLS = [
    "find_item",
    "get_inventory",
    "fridge_activity",
    "last_opened",
    "oldest_items",
    "low_stock",
]


# Thinking and markdown removed
def test_thinking_and_markdown_removed():
    raw = "<thinking>The user wants milk.</thinking>**Yes**, you have\n- 1 milk."
    assert assistant.clean(raw) == "Yes, you have 1 milk."


def test_numbered_list_markers_and_whitespace():
    assert assistant.clean("1. You have `2` eggs.\n\n2. And _1_ milk.  ") == (
        "You have 2 eggs. And 1 milk."
    )


def test_multiline_thinking_removed():
    assert assistant.clean("<thinking>a\nb</thinking>\n# Done") == "Done"


# Empty answer (cleanup side)
def test_thinking_only_is_empty():
    assert assistant.clean("<thinking>hmm</thinking>") == ""


# MCP URL
def test_mcp_url():
    host = "abc123.execute-api.us-east-1.amazonaws.com"
    assert assistant.mcp_url(host, "k1") == f"https://{host}/mcp/k1"


# Four tools offered (tool spec shape)
@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_tool_specs_from_mcp(aws, anyio_backend):
    def context():
        return FridgeContext(FridgeTable(), ACCOUNT, NOW, ZoneInfo("America/Toronto"))

    async with Client(build_server(context), mode="legacy") as client:
        tools = (await client.list_tools()).tools
    specs = assistant.tool_specs(tools)
    assert [s["toolSpec"]["name"] for s in specs] == [t.name for t in tools]
    assert sorted(s["toolSpec"]["name"] for s in specs) == sorted(TOOLS)
    for spec, tool in zip(specs, tools, strict=True):
        assert spec["toolSpec"]["description"] == tool.description
        assert spec["toolSpec"]["inputSchema"] == {"json": tool.input_schema}
