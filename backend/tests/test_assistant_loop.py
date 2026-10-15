"""fridge-assistant: the Converse tool-use loop against an in-process MCP server."""

from zoneinfo import ZoneInfo

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from fridgesense import assistant
from fridgesense.mcp_server import NOT_LINKED, FridgeContext, build_server
from fridgesense.table import FridgeTable
from tests.mcp_helpers import ACCOUNT, NOW, put_item

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


async def ask(question, server, stub, **kw):
    return await assistant.run(question, server=server, bedrock=stub.client, **kw)


def tool_results(request: dict) -> list[dict]:
    last = request["messages"][-1]
    assert last["role"] == "user"
    return [block["toolResult"] for block in last["content"] if "toolResult" in block]


# Four tools offered, Six tools offered
async def test_six_tools_offered(server, converse_stub):
    converse_stub.answer("end_turn_hello.json")
    await ask("Do I have milk?", server, converse_stub)
    tools = converse_stub.requests[0]["toolConfig"]["tools"]
    assert sorted(t["toolSpec"]["name"] for t in tools) == sorted(TOOLS)
    for t in tools:
        assert t["toolSpec"]["description"]
        assert t["toolSpec"]["inputSchema"]["json"]["type"] == "object"


# Do I have milk
async def test_do_i_have_milk(server, converse_stub):
    put_item("milk", 1, minutes_ago=2)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    result = await ask("Do I have milk?", server, converse_stub)

    assert result.answer == "Yes, you have 1 milk, added 2 minutes ago."
    assert result.tools == ["find_item"]
    assert len(converse_stub.requests) == 2
    first, second = converse_stub.requests
    assert first["messages"] == [{"role": "user", "content": [{"text": "Do I have milk?"}]}]
    # The model's tool-use turn is replayed as is, then one tool result for it.
    assert second["messages"][1]["role"] == "assistant"
    [res] = tool_results(second)
    assert res["toolUseId"] == "tu-milk"
    assert res["status"] == "success"
    data = res["content"][0]["json"]
    assert data["query"] == "milk"
    assert data["in_fridge"] is True
    assert data["total_count"] == 1
    converse_stub.stubber.assert_no_pending_responses()


# System prompt
async def test_system_prompt(server, converse_stub):
    converse_stub.answer("end_turn_hello.json")
    await ask("Hi", server, converse_stub)
    request = converse_stub.requests[0]
    system = " ".join(b["text"] for b in request["system"] if "text" in b).lower()
    assert "two short" in system
    assert "markdown" in system
    assert "tools" in system
    assert request["modelId"] == assistant.DEFAULT_MODEL_ID
    assert request["inferenceConfig"]["temperature"] <= 0.3


# No tool needed
async def test_no_tool_needed(server, converse_stub):
    converse_stub.answer("end_turn_hello.json")
    result = await ask("Hello", server, converse_stub)
    assert result.answer == "Hello! Ask me what's in your fridge."
    assert result.tools == []
    assert len(converse_stub.requests) == 1


# Open question combines tools
async def test_open_question_combines_tools(server, converse_stub):
    put_item("eggs", 6)
    put_item("milk", 1)
    converse_stub.answer("tool_use_inventory.json", "tool_use_find_eggs.json", "end_turn_cook.json")
    result = await ask("What can I cook tonight?", server, converse_stub)
    assert result.tools == ["get_inventory", "find_item"]
    assert result.answer == "You could make an omelette with your eggs and milk."
    [inv] = tool_results(converse_stub.requests[1])
    assert inv["content"][0]["json"]["total_items"] == 2
    [eggs] = tool_results(converse_stub.requests[2])
    assert eggs["toolUseId"] == "tu-eggs"


# Two tools in one turn
async def test_two_tools_in_one_turn(server, converse_stub):
    put_item("milk", 1)
    converse_stub.answer("tool_use_two_finds.json", "end_turn_milk.json")
    result = await ask("Do I have milk and eggs?", server, converse_stub)
    assert result.tools == ["find_item", "find_item"]
    second = converse_stub.requests[1]
    results = tool_results(second)
    assert [r["toolUseId"] for r in results] == ["tu-a", "tu-b"]
    assert [r["content"][0]["json"]["query"] for r in results] == ["milk", "eggs"]
    # One user message carries both results.
    assert len(second["messages"]) == 3


# No camera linked
async def test_tool_error_goes_back_to_model(aws, converse_stub):
    def not_linked():
        raise ToolError(NOT_LINKED)

    converse_stub.answer("tool_use_last_opened.json", "end_turn_not_linked.json")
    result = await ask("When was the fridge last opened?", build_server(not_linked), converse_stub)
    [res] = tool_results(converse_stub.requests[1])
    assert res["status"] == "error"
    assert NOT_LINKED in res["content"][0]["text"]
    assert result.answer == "No camera is linked yet, so I can't tell."
    assert result.tools == ["last_opened"]


CACHE_POINT = {"cachePoint": {"type": "default"}}


def cache_points(request: dict) -> list[dict]:
    blocks = list(request["system"])
    for message in request["messages"]:
        blocks += message["content"]
    return [b["cachePoint"] for b in blocks if "cachePoint" in b]


# First round
async def test_first_round_cache_points(server, converse_stub):
    converse_stub.answer("end_turn_hello.json")
    await ask("Do I have milk?", server, converse_stub)
    [first] = converse_stub.requests
    assert first["system"] == [{"text": assistant.SYSTEM_PROMPT}, CACHE_POINT]
    assert first["messages"] == [{"role": "user", "content": [{"text": "Do I have milk?"}]}]
    assert all(set(t) == {"toolSpec"} for t in first["toolConfig"]["tools"])


# Tool results carry no cache point
async def test_tool_results_carry_no_cache_point(server, converse_stub):
    put_item("milk", 1, minutes_ago=2)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    await ask("Do I have milk?", server, converse_stub)
    first, second = converse_stub.requests
    last = second["messages"][-1]
    assert last["role"] == "user"
    assert [next(iter(b)) for b in last["content"]] == ["toolResult"]
    assert not any("cachePoint" in b for m in second["messages"] for b in m["content"])
    assert second["system"] == first["system"]


# One cache point per request
async def test_one_cache_point_per_request(server, converse_stub):
    put_item("milk", 1, minutes_ago=2)
    converse_stub.answer(
        "tool_use_find_milk.json",
        "tool_use_find_milk.json",
        "tool_use_find_milk.json",
        "end_turn_milk.json",
    )
    await ask("Do I have milk?", server, converse_stub)
    fourth = converse_stub.requests[3]
    assert len(cache_points(fourth)) == 1
    assert fourth["system"][-1] == CACHE_POINT


# Cache points carry no ttl
async def test_cache_points_carry_no_ttl(server, converse_stub):
    put_item("milk", 1, minutes_ago=2)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    await ask("Do I have milk?", server, converse_stub)
    for request in converse_stub.requests:
        assert cache_points(request)
        assert all(point == {"type": "default"} for point in cache_points(request))
