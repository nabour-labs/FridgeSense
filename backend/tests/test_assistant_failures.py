"""fridge-assistant: failures, the round and time limits, and the per-question cost log."""

import json
import logging
from zoneinfo import ZoneInfo

import pytest

from fridgesense import assistant
from fridgesense.mcp_server import FridgeContext, build_server
from fridgesense.table import FridgeTable
from tests.mcp_helpers import ACCOUNT, NOW, put_item

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def server(aws):
    def context():
        return FridgeContext(FridgeTable(), ACCOUNT, NOW, ZoneInfo("America/Toronto"))

    return build_server(context)


class FakeClock:
    """Returns `times` in order, then keeps returning the last one."""

    def __init__(self, *times: float):
        self.times = list(times)

    def __call__(self) -> float:
        return self.times.pop(0) if len(self.times) > 1 else self.times[0]


def events(caplog, name: str) -> list[dict]:
    out = []
    for record in caplog.records:
        try:
            data = json.loads(record.getMessage())
        except ValueError:
            continue
        if data.get("event") == name:
            out.append(data)
    return out


async def ask(question, server, stub, **kw):
    return await assistant.run(question, server=server, bedrock=stub.client, **kw)


# Bedrock error
async def test_bedrock_error(server, converse_stub):
    converse_stub.fail("ThrottlingException")
    result = await ask("Do I have milk?", server, converse_stub)
    assert isinstance(result, assistant.AssistantFailure)
    assert result.reason == "bedrock_error"


# Too many rounds
async def test_too_many_rounds(server, converse_stub):
    put_item("milk", 1)
    converse_stub.answer(*["tool_use_find_milk.json"] * 4)
    result = await ask("Do I have milk?", server, converse_stub)
    assert result.reason == "too_many_rounds"
    assert len(converse_stub.requests) == 4
    converse_stub.stubber.assert_no_pending_responses()


# Too slow
async def test_too_slow(server, converse_stub):
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    # start, before the 1st model call, then past 12 s before the tool call
    clock = FakeClock(0.0, 1.0, 13.0)
    result = await ask("Do I have milk?", server, converse_stub, clock=clock)
    assert result.reason == "timeout"
    assert len(converse_stub.requests) == 1


async def test_real_deadline(server, converse_stub, monkeypatch):
    """A hung MCP call is cut off by the real deadline too, not only the clock checks."""
    import anyio

    async def hang(*_a, **_k):
        await anyio.sleep(5)

    monkeypatch.setattr("mcp.Client.call_tool", hang)
    converse_stub.answer("tool_use_find_milk.json")
    result = await ask("Do I have milk?", server, converse_stub, deadline_s=0.2)
    assert result.reason == "timeout"


# Empty answer
async def test_empty_answer(server, converse_stub):
    converse_stub.answer("end_turn_thinking_only.json")
    result = await ask("Do I have milk?", server, converse_stub)
    assert result.reason == "empty_answer"


# MCP server unreachable
async def test_mcp_unreachable(aws, converse_stub):
    result = await ask("Do I have milk?", "http://127.0.0.1:9/mcp/x", converse_stub)
    assert result.reason == "mcp_error"
    assert converse_stub.requests == []


# Answered question
async def test_cost_logged_for_answer(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json", "end_turn_milk.json")
    question = "Do I have milk?"
    url_like = "https://h/mcp/secret-key"
    await ask(question, server, converse_stub)

    [event] = events(caplog, "ask_agent")
    assert event["outcome"] == "answered"
    assert event["rounds"] == 2
    assert event["tools"] == ["find_item"]
    assert event["input_tokens"] == 2700
    assert event["output_tokens"] == 70
    assert event["usd"] == 0.001084
    assert isinstance(event["ms"], int)
    text = caplog.text
    assert question not in text
    assert url_like not in text


# Failed question still logs cost
async def test_cost_logged_for_failure(server, converse_stub, caplog):
    caplog.set_level(logging.INFO, logger="fridgesense")
    put_item("milk", 1)
    converse_stub.answer("tool_use_find_milk.json").fail("ThrottlingException")
    await ask("Do I have milk?", server, converse_stub)

    [event] = events(caplog, "ask_agent")
    assert event["outcome"] == "bedrock_error"
    assert event["input_tokens"] == 1200
    assert event["output_tokens"] == 40
